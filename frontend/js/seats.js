/**
 * Cineverse Interactive Seat Matrix Controller
 */

let showId = null;
let showData = null;
let seatMapData = [];
const selectedSeats = new Map(); // seatId -> seatObj
let currentHoldBooking = null;
let holdCountdownInterval = null;

const SEAT_TYPE_MULTIPLIERS = {
  regular: 1.0,
  premium: 1.4,
  recliner: 1.8,
};

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const sid = params.get("show_id");
  if (!sid) {
    showToast("No show selected. Redirecting to movies page...", "warning");
    setTimeout(() => (window.location.href = "/movies.html"), 1500);
    return;
  }

  showId = parseInt(sid, 10);
  initSeatMap();

  document.getElementById("hold-seats-btn").addEventListener("click", holdSelectedSeats);
  document.getElementById("proceed-payment-btn").addEventListener("click", () => {
    if (currentHoldBooking) {
      window.location.href = `/bookings.html?booking_id=${currentHoldBooking.id}`;
    }
  });
});

async function initSeatMap() {
  try {
    // 1. Fetch Show Details
    showData = await apiClient(`/api/shows/${showId}`);
    renderShowHeader(showData);

    // 2. Fetch Seat Grid Map
    await refreshSeats();
  } catch (err) {
    showToast(err.message || "Failed to load show details.", "error");
  }
}

function renderShowHeader(show) {
  const titleEl = document.getElementById("show-movie-title");
  const subEl = document.getElementById("show-details-sub");

  titleEl.textContent = show.movie ? show.movie.title : `Show #${show.id}`;
  const dt = new Date(show.start_time);
  const timeStr = dt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  const dateStr = dt.toLocaleDateString("en-IN", { weekday: "short", month: "short", day: "numeric" });
  const theatreName = show.theatre ? `${show.theatre.name} (${show.screen ? show.screen.name : ''})` : (show.screen ? `${show.screen.theatre_name || 'Cineverse'} (${show.screen.name})` : "Main Screen");

  subEl.textContent = `${dateStr} at ${timeStr} • ${theatreName} • Base Price: ₹${parseFloat(show.base_price).toFixed(2)}`;
}

async function refreshSeats() {
  const matrixContainer = document.getElementById("seat-matrix");
  try {
    seatMapData = await apiClient(`/api/shows/${showId}/seats`);

    // Group seats by row_label
    const rows = {};
    seatMapData.forEach((s) => {
      if (!rows[s.row_label]) rows[s.row_label] = [];
      rows[s.row_label].push(s);
    });

    // Sort rows alphabetically and seats by number
    const sortedRowLabels = Object.keys(rows).sort();

    matrixContainer.innerHTML = sortedRowLabels.map((rowLabel) => {
      const seatsInRow = rows[rowLabel].sort((a, b) => a.seat_number - b.seat_number);
      return `
        <div class="seat-row">
          <span class="row-label">${escapeHtml(rowLabel)}</span>
          ${seatsInRow.map((seat) => {
            const isSelected = selectedSeats.has(seat.id);
            let statusClass = seat.status;
            if (isSelected) statusClass = "selected";

            return `
              <div 
                class="seat ${statusClass}" 
                data-seat-id="${seat.id}"
                title="${escapeHtml(seat.row_label)}${seat.seat_number} - ${escapeHtml(seat.seat_type.toUpperCase())} (₹${parseFloat(seat.price).toFixed(0)})"
                onclick="toggleSeatSelection(${seat.id})"
              >
                ${seat.seat_number}
              </div>
            `;
          }).join("")}
        </div>
      `;
    }).join("");

    updateSummary();
  } catch (err) {
    matrixContainer.innerHTML = `<p style="color: var(--accent-red);">Failed to load seats: ${escapeHtml(err.message)}</p>`;
  }
}

function toggleSeatSelection(seatId) {
  if (currentHoldBooking) {
    showToast("Seats are currently held. Proceed to payment or wait for timer expiration.", "warning");
    return;
  }

  const seat = seatMapData.find((s) => s.id === seatId);
  if (!seat) return;

  if (seat.status !== "available") {
    showToast(`Seat ${seat.row_label}${seat.seat_number} is ${seat.status} and cannot be selected.`, "error");
    return;
  }

  if (selectedSeats.has(seatId)) {
    selectedSeats.delete(seatId);
  } else {
    if (selectedSeats.size >= 6) {
      showToast("Maximum 6 seats allowed per booking.", "warning");
      return;
    }
    selectedSeats.set(seatId, seat);
  }

  // Update visual DOM
  const seatEl = document.querySelector(`.seat[data-seat-id="${seatId}"]`);
  if (seatEl) {
    if (selectedSeats.has(seatId)) {
      seatEl.classList.remove("available");
      seatEl.classList.add("selected");
    } else {
      seatEl.classList.remove("selected");
      seatEl.classList.add("available");
    }
  }

  updateSummary();
}

function updateSummary() {
  const pillsContainer = document.getElementById("selected-seats-pills");
  const holdBtn = document.getElementById("hold-seats-btn");
  const subtotalEl = document.getElementById("summary-subtotal");
  const weekendEl = document.getElementById("summary-weekend");
  const feeEl = document.getElementById("summary-fee");
  const totalEl = document.getElementById("summary-total");

  if (selectedSeats.size === 0) {
    pillsContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">No seats selected</span>`;
    holdBtn.disabled = true;
    subtotalEl.textContent = "₹0.00";
    weekendEl.textContent = "₹0.00";
    feeEl.textContent = "₹0.00";
    totalEl.textContent = "₹0.00";
    return;
  }

  holdBtn.disabled = false;
  const seatsList = Array.from(selectedSeats.values());

  pillsContainer.innerHTML = seatsList.map((s) => `
    <span class="status-badge confirmed" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;">
      ${escapeHtml(s.row_label)}${s.seat_number} (${escapeHtml(s.seat_type[0].toUpperCase())})
    </span>
  `).join("");

  // Calculate pricing breakdown
  const basePrice = parseFloat(showData.base_price);
  const showDate = new Date(showData.start_time);
  const dayOfWeek = showDate.getDay(); // 0 = Sun, 5 = Fri, 6 = Sat
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 5 || dayOfWeek === 6;

  let rawSubtotal = 0;
  seatsList.forEach((s) => {
    const mult = SEAT_TYPE_MULTIPLIERS[s.seat_type.toLowerCase()] || 1.0;
    rawSubtotal += basePrice * mult;
  });

  const weekendSurcharge = isWeekend ? rawSubtotal * 0.10 : 0.0;
  const subtotalWithWeekend = rawSubtotal + weekendSurcharge;
  const convenienceFee = subtotalWithWeekend * 0.02;
  const totalAmount = Math.round((subtotalWithWeekend + convenienceFee) * 100) / 100;

  subtotalEl.textContent = `₹${rawSubtotal.toFixed(2)}`;
  weekendEl.textContent = `₹${weekendSurcharge.toFixed(2)}`;
  feeEl.textContent = `₹${convenienceFee.toFixed(2)}`;
  totalEl.textContent = `₹${totalAmount.toFixed(2)}`;
}

async function holdSelectedSeats() {
  if (selectedSeats.size === 0) return;
  const holdBtn = document.getElementById("hold-seats-btn");
  const proceedBtn = document.getElementById("proceed-payment-btn");

  const seatIds = Array.from(selectedSeats.keys());
  const userId = getCurrentUserId();

  holdBtn.disabled = true;
  holdBtn.textContent = "Holding Seats...";

  try {
    const booking = await apiClient("/api/bookings", {
      method: "POST",
      body: {
        user_id: userId,
        show_id: showId,
        seat_ids: seatIds,
      },
    });

    currentHoldBooking = booking;
    showToast(`Seats held successfully! Reference #${booking.id}`, "success");

    // Start 5-minute countdown
    startHoldTimer(new Date(booking.expires_at));

    holdBtn.style.display = "none";
    proceedBtn.style.display = "block";
    proceedBtn.textContent = `Proceed to Payment (₹${parseFloat(booking.total_amount).toFixed(2)}) →`;
  } catch (err) {
    holdBtn.disabled = false;
    holdBtn.textContent = "Hold Seats (5 Mins)";
    showToast(err.message || "Failed to hold seats. Someone may have just reserved them.", "error");
    await refreshSeats();
  }
}

function startHoldTimer(expiresAt) {
  const banner = document.getElementById("hold-banner");
  const digits = document.getElementById("hold-countdown");
  banner.style.display = "flex";

  if (holdCountdownInterval) clearInterval(holdCountdownInterval);

  holdCountdownInterval = setInterval(() => {
    const now = new Date();
    const remainingMs = expiresAt.getTime() - now.getTime();

    if (remainingMs <= 0) {
      clearInterval(holdCountdownInterval);
      digits.textContent = "00:00";
      showToast("Hold expired. Seats have been released.", "error");
      setTimeout(() => window.location.reload(), 1500);
      return;
    }

    const totalSeconds = Math.floor(remainingMs / 1000);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    digits.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }, 1000);
}
