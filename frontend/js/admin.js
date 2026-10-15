/**
 * Cineverse Admin Portal Controller
 */

let cachedMovies = [];
let cachedTheatres = [];

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardData();
  setupInitialDateTime();
});

function setupInitialDateTime() {
  const dtInput = document.getElementById("s-start-time");
  if (dtInput) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(18, 0, 0, 0);
    dtInput.value = tomorrow.toISOString().slice(0, 16);
  }
}

async function loadDashboardData() {
  try {
    // 1. Load Movies
    const moviesData = await apiClient("/api/movies?page=1&page_size=50");
    cachedMovies = moviesData.items || [];
    document.getElementById("stat-movies").textContent = cachedMovies.length;
    renderAdminMoviesTable(cachedMovies);
    populateMovieDropdown(cachedMovies);

    // 2. Load Theatres and Screens
    cachedTheatres = await apiClient("/api/theatres");
    populateScreensDropdown(cachedTheatres);

    // 3. Load Bookings stats across demo users to compute total revenue
    let totalRevenue = 0;
    let totalBookings = 0;

    for (const user of DEMO_USERS) {
      try {
        const userBookings = await apiClient(`/api/users/${user.id}/bookings`);
        userBookings.forEach((b) => {
          if (b.status === "confirmed") {
            totalRevenue += parseFloat(b.total_amount);
            totalBookings += 1;
          }
        });
      } catch (err) {
        // Skip uncreated users
      }
    }

    document.getElementById("stat-revenue").textContent = `₹${totalRevenue.toFixed(2)}`;
    document.getElementById("stat-bookings").textContent = totalBookings;
  } catch (err) {
    showToast(err.message || "Failed to load admin stats.", "error");
  }
}

function renderAdminMoviesTable(movies) {
  const tbody = document.getElementById("admin-movies-tbody");
  if (movies.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No movies registered.</td></tr>`;
    return;
  }

  tbody.innerHTML = movies.map((m) => `
    <tr>
      <td>${m.id}</td>
      <td><strong>${escapeHtml(m.title)}</strong></td>
      <td>${escapeHtml(m.genre)}</td>
      <td>${escapeHtml(m.language)}</td>
      <td>${m.duration_min} min</td>
      <td><span class="status-badge" style="background: rgba(245, 197, 24, 0.15); color: var(--accent-gold); border: 1px solid rgba(245, 197, 24, 0.3);">${escapeHtml(m.rating)}</span></td>
      <td><span class="status-badge ${m.is_active ? 'confirmed' : 'cancelled'}">${m.is_active ? 'Active' : 'Archived'}</span></td>
      <td>
        ${m.is_active ? `
          <button class="btn btn-danger btn-sm" onclick="deactivateMovie(${m.id})">Deactivate</button>
        ` : `
          <span style="color: var(--text-muted); font-size: 0.8rem;">Archived</span>
        `}
      </td>
    </tr>
  `).join("");
}

function populateMovieDropdown(movies) {
  const select = document.getElementById("s-movie-select");
  select.innerHTML = '<option value="">-- Select Movie --</option>';
  movies.forEach((m) => {
    if (m.is_active) {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.title} (${m.duration_min} min - ${m.language})`;
      select.appendChild(opt);
    }
  });
}

function populateScreensDropdown(theatres) {
  const select = document.getElementById("s-screen-select");
  select.innerHTML = '<option value="">-- Select Auditorium Screen --</option>';

  theatres.forEach((t) => {
    if (t.screens) {
      t.screens.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = `${t.name} - ${s.name} (${t.city})`;
        select.appendChild(opt);
      });
    }
  });
}

async function submitMovie() {
  const btn = document.getElementById("add-movie-btn");
  btn.disabled = true;
  btn.textContent = "Creating Movie...";

  const payload = {
    title: document.getElementById("m-title").value.trim(),
    genre: document.getElementById("m-genre").value.trim(),
    language: document.getElementById("m-lang").value.trim(),
    duration_min: parseInt(document.getElementById("m-duration").value, 10),
    rating: document.getElementById("m-rating").value,
    poster_url: document.getElementById("m-poster").value.trim() || null,
    description: document.getElementById("m-desc").value.trim(),
    release_date: new Date().toISOString().split("T")[0],
  };

  try {
    const created = await apiClient("/api/movies", {
      method: "POST",
      body: payload,
    });
    showToast(`Movie '${created.title}' added successfully!`, "success");
    document.getElementById("add-movie-form").reset();
    loadDashboardData();
  } catch (err) {
    showToast(err.message || "Failed to create movie.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Create Movie Listing";
  }
}

async function deactivateMovie(movieId) {
  if (!confirm("Are you sure you want to archive this movie listing?")) return;

  try {
    await apiClient(`/api/movies/${movieId}`, {
      method: "DELETE",
    });
    showToast("Movie successfully archived.", "success");
    loadDashboardData();
  } catch (err) {
    showToast(err.message || "Failed to archive movie.", "error");
  }
}

async function submitShow() {
  const btn = document.getElementById("schedule-show-btn");
  const movieId = parseInt(document.getElementById("s-movie-select").value, 10);
  const screenId = parseInt(document.getElementById("s-screen-select").value, 10);
  const startTimeVal = document.getElementById("s-start-time").value;
  const basePrice = parseFloat(document.getElementById("s-price").value);

  if (!movieId || !screenId || !startTimeVal) {
    showToast("Please fill all required show fields.", "warning");
    return;
  }

  const selectedMovie = cachedMovies.find((m) => m.id === movieId);
  const duration = selectedMovie ? selectedMovie.duration_min : 120;

  const startDt = new Date(startTimeVal);
  const endDt = new Date(startDt.getTime() + (duration + 20) * 60000);

  btn.disabled = true;
  btn.textContent = "Verifying Screen Availability...";

  try {
    const show = await apiClient("/api/shows", {
      method: "POST",
      body: {
        movie_id: movieId,
        screen_id: screenId,
        start_time: startDt.toISOString(),
        end_time: endDt.toISOString(),
        base_price: basePrice,
      },
    });

    showToast(`Show scheduled successfully (ID #${show.id})!`, "success");
    setupInitialDateTime();
  } catch (err) {
    showToast(err.message || "Screen scheduling conflict detected.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Schedule Show";
  }
}
