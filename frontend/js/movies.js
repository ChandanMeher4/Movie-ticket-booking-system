/**
 * Cineverse Movies Catalog & Showtimes Controller
 */

let currentPage = 1;
const pageSize = 8;

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("movie-search-input");
  const genreFilter = document.getElementById("genre-filter");
  const languageFilter = document.getElementById("language-filter");
  const sortFilter = document.getElementById("sort-filter");
  const resetBtn = document.getElementById("reset-filters-btn");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const modal = document.getElementById("showtimes-modal");

  // Debounced search
  let debounceTimeout = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      currentPage = 1;
      fetchMovies();
    }, 300);
  });

  genreFilter.addEventListener("change", () => {
    currentPage = 1;
    fetchMovies();
  });

  languageFilter.addEventListener("change", () => {
    currentPage = 1;
    fetchMovies();
  });

  sortFilter.addEventListener("change", () => {
    currentPage = 1;
    fetchMovies();
  });

  resetBtn.addEventListener("click", () => {
    searchInput.value = "";
    genreFilter.value = "";
    languageFilter.value = "";
    sortFilter.value = "release_date_desc";
    currentPage = 1;
    fetchMovies();
  });

  closeModalBtn.addEventListener("click", () => {
    modal.style.display = "none";
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  // Check URL params for direct movie_id selection
  const urlParams = new URLSearchParams(window.location.search);
  const directMovieId = urlParams.get("movie_id");
  if (directMovieId) {
    openShowtimesModal(parseInt(directMovieId, 10));
  }

  fetchMovies();
});

async function fetchMovies() {
  const container = document.getElementById("movies-container");
  const pagination = document.getElementById("pagination-controls");
  const search = document.getElementById("movie-search-input").value.trim();
  const genre = document.getElementById("genre-filter").value;
  const language = document.getElementById("language-filter").value;
  const sort = document.getElementById("sort-filter").value;

  const [sortField, sortDir] = sort.split("_");

  let url = `/api/movies?page=${currentPage}&page_size=${pageSize}&sort_by=${sortField}&sort_order=${sortDir}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (genre) url += `&genre=${encodeURIComponent(genre)}`;
  if (language) url += `&language=${encodeURIComponent(language)}`;

  try {
    container.innerHTML = "<p style='color: var(--text-muted); grid-column: 1/-1;'>Loading movie catalog...</p>";
    const data = await apiClient(url);

    if (!data.items || data.items.length === 0) {
      container.innerHTML = "<p style='color: var(--text-muted); grid-column: 1/-1;'>No movies match your filters. Try adjusting your query.</p>";
      pagination.innerHTML = "";
      return;
    }

    container.innerHTML = data.items.map((m) => `
      <div class="movie-card">
        <div class="movie-poster-wrap">
          <img class="movie-poster" src="${escapeHtml(m.poster_url || 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=500')}" alt="${escapeHtml(m.title)} poster" loading="lazy">
          <span class="movie-rating-badge">${escapeHtml(m.rating)}</span>
        </div>
        <div class="movie-card-body">
          <h3 class="movie-title">${escapeHtml(m.title)}</h3>
          <div class="movie-meta">
            <span>${escapeHtml(m.genre)}</span>
            <span>&bull;</span>
            <span>${m.duration_min} min</span>
            <span>&bull;</span>
            <span>${escapeHtml(m.language)}</span>
          </div>
          <p class="movie-desc">${escapeHtml(m.description)}</p>
          <div style="margin-top: auto; display: flex; gap: 0.5rem;">
            <button class="btn btn-primary btn-sm" style="flex: 1;" onclick="openShowtimesModal(${m.id})">
              Check Showtimes
            </button>
          </div>
        </div>
      </div>
    `).join("");

    renderPagination(data.page, data.total_pages);
  } catch (err) {
    container.innerHTML = `<p style="color: var(--accent-red); grid-column: 1/-1;">Error loading movies: ${escapeHtml(err.message)}</p>`;
  }
}

function renderPagination(page, totalPages) {
  const container = document.getElementById("pagination-controls");
  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = "";
  if (page > 1) {
    html += `<button class="btn btn-secondary btn-sm" onclick="goToPage(${page - 1})">&laquo; Prev</button>`;
  }

  html += `<span style="color: var(--text-secondary); font-size: 0.9rem; margin: 0 0.75rem;">Page ${page} of ${totalPages}</span>`;

  if (page < totalPages) {
    html += `<button class="btn btn-secondary btn-sm" onclick="goToPage(${page + 1})">Next &raquo;</button>`;
  }

  container.innerHTML = html;
}

function goToPage(newPage) {
  currentPage = newPage;
  fetchMovies();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function openShowtimesModal(movieId) {
  const modal = document.getElementById("showtimes-modal");
  const modalTitle = document.getElementById("modal-movie-title");
  const modalMeta = document.getElementById("modal-movie-meta");
  const modalContent = document.getElementById("modal-showtimes-content");

  modal.style.display = "flex";
  modalContent.innerHTML = "<p style='color: var(--text-muted);'>Loading showtimes...</p>";

  try {
    const movie = await apiClient(`/api/movies/${movieId}`);
    modalTitle.textContent = movie.title;
    modalMeta.textContent = `${movie.genre} • ${movie.duration_min} min • ${movie.rating} • ${movie.language}`;

    const showsData = await apiClient(`/api/shows?movie_id=${movieId}`);
    const shows = showsData.items || [];

    if (shows.length === 0) {
      modalContent.innerHTML = "<p style='color: var(--text-muted);'>No upcoming showtimes are scheduled for this title.</p>";
      return;
    }

    // Group shows by theatre name
    const grouped = {};
    shows.forEach((s) => {
      const theatre = s.screen ? `${s.screen.theatre_name || 'Cineverse'} (${s.screen.theatre_city || 'City'})` : "Cineverse Multiplex";
      if (!grouped[theatre]) grouped[theatre] = [];
      grouped[theatre].push(s);
    });

    let html = "";
    for (const [theatre, showList] of Object.entries(grouped)) {
      html += `
        <div style="background-color: var(--bg-surface-elevated); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
          <h4 style="color: var(--accent-gold); font-size: 1.05rem; margin-bottom: 0.85rem;">${escapeHtml(theatre)}</h4>
          <div style="display: flex; flex-wrap: wrap; gap: 0.75rem;">
            ${showList.map((s) => {
              const dt = new Date(s.start_time);
              const timeStr = dt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
              const dateStr = dt.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
              return `
                <a href="/seats.html?show_id=${s.id}" class="btn btn-secondary btn-sm" style="display: flex; flex-direction: column; align-items: center; padding: 0.6rem 0.9rem; text-decoration: none;">
                  <span style="font-weight: 700; color: #fff;">${timeStr}</span>
                  <span style="font-size: 0.72rem; color: var(--text-muted);">${dateStr} &bull; ${escapeHtml(s.screen ? s.screen.name : 'Screen')}</span>
                  <span style="font-size: 0.78rem; color: var(--accent-green); font-weight: 600;">₹${parseFloat(s.base_price).toFixed(0)}</span>
                </a>
              `;
            }).join("")}
          </div>
        </div>
      `;
    }
    modalContent.innerHTML = html;
  } catch (err) {
    modalContent.innerHTML = `<p style="color: var(--accent-red);">Failed to load showtimes: ${escapeHtml(err.message)}</p>`;
  }
}
