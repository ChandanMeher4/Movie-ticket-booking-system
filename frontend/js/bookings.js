/**
 * Cineverse Bookings & Checkout Controller
 */

let activeCheckoutBooking = null;
let pendingCancelBookingId = null;

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const bid = params.get("booking_id");
  if (bid) {
    loadCheckout(parseInt(bid, 10));
  }

  loadUserBookings();

  document.getElementById("cancel-modal-close").addEventListener("click", () => {
    document.getElementById("cancel-modal").style.display = "none";
  });

  document.getElementById("confirm-cancel-btn").addEventListener("click", executeCancellation);
});

// Re-fetch bookings if user switches profile
function onUserChanged() {
  loadUserBookings();
}

async function loadCheckout(bookingId) {
  try {
    const booking = await apiClient(`/api/bookings/${bookingId}`);
    activeCheckoutBooking = booking;

    if (booking.status === "confirmed") {
      showVoucher(booking, "Already Confirmed");
      return;
    }

    if (booking.status === "cancelled") {
      showToast("This booking hold has expired or was cancelled.", "error");
      return;
    }

    document.getElementById("checkout-section").style.display = "block";
    document.getElementById("chk-ref").textContent = `#${booking.id}`;
    const chkTheatreName = (booking.show && booking.show.theatre) ? `${booking.show.theatre.name} (${booking.show.screen ? booking.show.screen.name : ''})` : (booking.show && booking.show.screen ? `${booking.show.screen.theatre_name || 'Cineverse'} (${booking.show.screen.name})` : "Auditorium");
    document.getElementById("chk-theatre").textContent = chkTheatreName;
    
    const showDt = booking.show ? new Date(booking.show.start_time) : new Date();
    document.getElementById("chk-time").textContent = showDt.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

    const seatNames = booking.booking_seats ? booking.booking_seats.map(bs => `${bs.seat.row_label}${bs.seat.seat_number}`).join(", ") : "N/A";
    document.getElementById("chk-seats").textContent = seatNames;
    document.getElementById("chk-amount").textContent = `₹${parseFloat(booking.total_amount).toFixed(2)}`;

    document.getElementById("pay-now-btn").textContent = `Pay ₹${parseFloat(booking.total_amount).toFixed(2)} & Confirm`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (err) {
    showToast(err.message || "Failed to load booking details.", "error");
  }
}

async function processPayment() {
  if (!activeCheckoutBooking) return;
  const payBtn = document.getElementById("pay-now-btn");
  const method = document.getElementById("payment-method-select").value;

  payBtn.disabled = true;
  payBtn.textContent = "Authorizing Transaction...";

  try {
    const payment = await apiClient("/api/payments", {
      method: "POST",
      body: {
        booking_id: activeCheckoutBooking.id,
        amount: activeCheckoutBooking.total_amount,
        method: method,
        payment_method: method,
      },
    });

    showToast("Payment authorized successfully!", "success");
    document.getElementById("checkout-section").style.display = "none";
    
    // Refresh booking object
    const updatedBooking = await apiClient(`/api/bookings/${activeCheckoutBooking.id}`);
    showVoucher(updatedBooking, payment.txn_ref);
    loadUserBookings();
  } catch (err) {
    payBtn.disabled = false;
    payBtn.textContent = `Pay ₹${parseFloat(activeCheckoutBooking.total_amount).toFixed(2)} & Confirm`;
    showToast(err.message || "Payment authorization failed.", "error");
  }
}

function showVoucher(booking, txnRef) {
  const section = document.getElementById("voucher-section");
  const details = document.getElementById("voucher-details");
  section.style.display = "block";

  const movieTitle = booking.show && booking.show.movie ? booking.show.movie.title : "Screening";
  const seatNames = booking.booking_seats ? booking.booking_seats.map(bs => `${bs.seat.row_label}${bs.seat.seat_number}`).join(", ") : "N/A";
  const showTime = booking.show ? formatDateTime(booking.show.start_time) : "N/A";

  details.innerHTML = `
    <div><strong>Booking Reference:</strong> #${booking.id}</div>
    <div><strong>Movie:</strong> ${escapeHtml(movieTitle)}</div>
    <div><strong>Showtime:</strong> ${escapeHtml(showTime)}</div>
    <div><strong>Allocated Seats:</strong> <span style="color: var(--accent-gold); font-weight: 700;">${escapeHtml(seatNames)}</span></div>
    <div><strong>Total Amount:</strong> ₹${parseFloat(booking.total_amount).toFixed(2)} (Paid)</div>
    <div><strong>Transaction Reference:</strong> <code style="background: var(--bg-surface-elevated); padding: 2px 6px; border-radius: 4px;">${escapeHtml(txnRef)}</code></div>
  `;
}

async function loadUserBookings() {
  const tbody = document.getElementById("bookings-table-body");
  const userId = getCurrentUserId();

  try {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Fetching reservations for user ID ${userId}...</td></tr>`;
    const bookings = await apiClient(`/api/users/${userId}/bookings`);

    if (!bookings || bookings.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No bookings found for your account.</td></tr>`;
      return;
    }

    tbody.innerHTML = bookings.map((b) => {
      const movieTitle = b.show && b.show.movie ? b.show.movie.title : `Show #${b.show_id}`;
      const showDt = b.show ? new Date(b.show.start_time) : null;
      const theatreStr = (b.show && b.show.theatre) ? `${b.show.theatre.name} (${b.show.screen ? b.show.screen.name : ''})` : (b.show && b.show.screen ? `${b.show.screen.theatre_name || 'Cineverse'} (${b.show.screen.name})` : "Screen");
      const seatsStr = b.booking_seats ? b.booking_seats.map(bs => `${bs.seat.row_label}${bs.seat.seat_number}`).join(", ") : "N/A";
      
      const now = new Date();
      const hoursUntilShow = showDt ? (showDt.getTime() - now.getTime()) / (1000 * 60 * 60) : 0;
      const canCancel = b.status === "confirmed" && hoursUntilShow > 2.0;

      let actionHtml = `<span style="color: var(--text-muted); font-size: 0.8rem;">None</span>`;
      if (b.status === "pending") {
        actionHtml = `<a href="/bookings.html?booking_id=${b.id}" class="btn btn-gold btn-sm">Pay Now</a>`;
      } else if (canCancel) {
        actionHtml = `<button class="btn btn-danger btn-sm" onclick="promptCancel(${b.id}, ${hoursUntilShow.toFixed(1)}, ${parseFloat(b.total_amount)})">Cancel</button>`;
      } else if (b.status === "confirmed" && hoursUntilShow <= 2.0) {
        actionHtml = `<span style="color: var(--text-muted); font-size: 0.78rem;" title="Non-refundable within 2h of showtime">Locked (&lt;2h)</span>`;
      }

      return `
        <tr>
          <td>#${b.id}</td>
          <td><strong>${escapeHtml(movieTitle)}</strong></td>
          <td>${escapeHtml(showStr)}</td>
          <td>${escapeHtml(theatreStr)}</td>
          <td><span style="color: var(--accent-gold); font-weight: 600;">${escapeHtml(seatsStr)}</span></td>
          <td><strong>₹${parseFloat(b.total_amount).toFixed(2)}</strong></td>
          <td><span class="status-badge ${b.status}">${escapeHtml(b.status)}</span></td>
          <td>${actionHtml}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--accent-red);">Failed to load bookings: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function promptCancel(bookingId, hoursUntilShow, totalAmount) {
  pendingCancelBookingId = bookingId;
  const modal = document.getElementById("cancel-modal");
  const summaryEl = document.getElementById("cancel-policy-summary");

  let refundPct = 0;
  if (hoursUntilShow > 24) {
    refundPct = 100;
  } else if (hoursUntilShow >= 2) {
    refundPct = 50;
  }

  // Base refund calculation (excluding 2% convenience fee if 100%)
  const estimatedRefund = (totalAmount * (refundPct / 100)).toFixed(2);

  summaryEl.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
      <div><strong>Booking ID:</strong> #${bookingId}</div>
      <div><strong>Showtime Status:</strong> Starts in ~${hoursUntilShow} hours</div>
      <div><strong>Applicable Refund Tier:</strong> <span style="color: var(--accent-green); font-weight: 700;">${refundPct}% Refund</span></div>
      <div><strong>Estimated Refund Amount:</strong> <span style="font-size: 1.15rem; color: var(--accent-green); font-weight: 800;">₹${estimatedRefund}</span></div>
      <p style="margin-top: 0.5rem; font-size: 0.82rem; color: var(--text-muted);">
        Refunds are credited immediately back to your original payment method. Convenience fees (2%) are non-refundable.
      </p>
    </div>
  `;

  modal.style.display = "flex";
}

async function executeCancellation() {
  if (!pendingCancelBookingId) return;
  const btn = document.getElementById("confirm-cancel-btn");
  btn.disabled = true;
  btn.textContent = "Processing Refund...";

  try {
    const res = await apiClient(`/api/bookings/${pendingCancelBookingId}/cancel`, {
      method: "POST",
    });

    document.getElementById("cancel-modal").style.display = "none";
    showToast(`Booking cancelled. Refund of ₹${parseFloat(res.refund_amount).toFixed(2)} (${res.refund_percentage}%) processed.`, "success");
    loadUserBookings();
  } catch (err) {
    showToast(err.message || "Failed to cancel booking.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Cancel & Refund";
    pendingCancelBookingId = null;
  }
}
