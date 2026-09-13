/**
 * jobbot app.js
 * Progressive enhancement: server renders HTML, JS adds smooth routing and interactivity.
 */

class App {
  constructor() {
    this.currentPage = null;
    this.isLoading = false;
    this.init();
  }

  async init() {
    console.log("jobbot app initialized");
    
    // Set up nav links
    this.setupNav();
    
    // Set up internal link handling
    this.setupRouting();
    
    // Mark current page as active
    this.updateActiveNav();
  }

  setupNav() {
    const nav = document.querySelector("nav[role='navigation'], nav[aria-label='main']");
    if (!nav) return;

    const links = nav.querySelectorAll("a");
    links.forEach(link => {
      link.addEventListener("click", (e) => {
        const href = link.getAttribute("href");
        if (href && href.startsWith("/")) {
          e.preventDefault();
          this.navigate(href);
        }
      });
    });
  }

  setupRouting() {
    // Intercept all internal navigation
    document.addEventListener("click", (e) => {
      const link = e.target.closest("a");
      if (!link) return;

      const href = link.getAttribute("href");
      if (href && href.startsWith("/") && !href.startsWith("//")) {
        e.preventDefault();
        this.navigate(href);
      }
    });

    // Handle back button
    window.addEventListener("popstate", (e) => {
      this.loadPage(window.location.pathname, false);
    });
  }

  updateActiveNav() {
    const currentPath = window.location.pathname;
    const links = document.querySelectorAll("nav a");
    
    links.forEach(link => {
      const href = link.getAttribute("href");
      if (href === currentPath || (currentPath === "/" && href === "/")) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  }

  async navigate(path) {
    window.history.pushState({}, "", path);
    await this.loadPage(path, true);
  }

  async loadPage(path, showSkeleton = true) {
    if (this.isLoading) return;

    this.isLoading = true;
    this.currentPage = path;

    try {
      // Show skeleton loaders
      if (showSkeleton) {
        this.showSkeletons();
      }

      // Fetch the page
      const response = await fetch(path, {
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      if (!response.ok) {
        if (response.status === 404) {
          this.showError("Page not found", "The page you're looking for doesn't exist.");
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const html = await response.text();

      // Update main content
      const main = document.querySelector("main, [role='main']");
      if (main) {
        // Replace content, keeping nav
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");
        const newMain = doc.querySelector("main, [role='main']");
        
        if (newMain) {
          main.innerHTML = newMain.innerHTML;
        } else {
          // Fallback: use the entire parsed body
          main.innerHTML = doc.body.innerHTML;
        }
      }

      // Update title
      const titleMatch = html.match(/<title[^>]*>([^<]*)<\/title>/i);
      if (titleMatch) {
        document.title = titleMatch[1];
      }

      // Update active nav
      this.updateActiveNav();

      // Scroll to top
      window.scrollTo(0, 0);

    } catch (error) {
      console.error("Navigation error:", error);
      this.showError("Loading failed", error.message);
    } finally {
      this.isLoading = false;
      this.hideSkeletons();
    }
  }

  showSkeletons() {
    const main = document.querySelector("main, [role='main']");
    if (!main) return;

    // Add skeleton loaders
    const skeletons = document.createElement("div");
    skeletons.className = "skeleton-container";
    skeletons.innerHTML = `
      <div class="skeleton" style="height: 2rem; margin-bottom: 1rem; width: 80%;"></div>
      <div class="skeleton" style="height: 1rem; margin-bottom: 0.5rem;"></div>
      <div class="skeleton" style="height: 1rem; margin-bottom: 0.5rem;"></div>
      <div class="skeleton" style="height: 1rem; margin-bottom: 2rem; width: 60%;"></div>
      <div class="skeleton" style="height: 1rem;"></div>
    `;
    
    // Store original content
    if (!main.dataset.originalContent) {
      main.dataset.originalContent = main.innerHTML;
    }

    main.innerHTML = skeletons.innerHTML;
  }

  hideSkeletons() {
    // Skeletons are replaced by actual content, nothing to do
  }

  showError(title, message) {
    const main = document.querySelector("main, [role='main']");
    if (main) {
      main.innerHTML = `
        <div data-component="empty" class="empty-state">
          <h2>${title}</h2>
          <p>${message}</p>
          <button onclick="window.location.href = '/'">Back to overview</button>
        </div>
      `;
    }
  }

  // Public API for tests
  static getCurrentPage() {
    return window.location.pathname;
  }

  static navigate(path) {
    if (window.app) {
      window.app.navigate(path);
    }
  }
}

// Initialize app when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    window.app = new App();
  });
} else {
  window.app = new App();
}

// Export for testing
if (typeof module !== "undefined" && module.exports) {
  module.exports = App;
}
