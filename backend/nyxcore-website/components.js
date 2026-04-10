/* ============================================
   NYX CORE FinAI — Shared Components
   Navigation, Footer, Animations & Utilities
   ============================================ */

// Hexagonal teal logo SVG
const LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="27" fill="none" viewBox="0 0 48 46"><path fill="#00d4aa" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"/></svg>`;

// Social media icons (simple SVG)
const SOCIAL_ICONS = {
  linkedin: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.225 0z"/></svg>`,
  github: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v 3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>`,
  twitter: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M23.953 4.57a10 10 0 002.856-9.898a9.958 9.958 0 01-2.821.856a4.958 4.958 0 00-8.618 4.53a14.07 14.07 0 01-10.211-5.251a4.95 4.95 0 001.524 6.573a4.914 4.914 0 01-2.24-.616c-.054 2.281 1.581 4.415 3.949 4.89a4.935 4.935 0 01-2.224.084a4.928 4.928 0 004.6 3.419A9.9 9.9 0 010 19.54a13.94 13.94 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/></svg>`
};

// Detect current page for nav highlighting
const currentPage = window.location.pathname.split('/').pop() || 'index.html';

function isActive(page) {
  if (page === 'index.html' && (currentPage === '' || currentPage === '/' || currentPage === 'index.html')) return true;
  return currentPage === page;
}

/* ========== NAVIGATION ========== */
function renderNav() {
  const nav = document.createElement('nav');
  nav.className = 'navbar';
  nav.innerHTML = `
    <div class="container">
      <div class="nav-inner">
        <a href="index.html" class="nav-logo">
          ${LOGO_SVG}
          <span>NYX <span class="logo-accent">CORE</span></span>
        </a>
        <div class="nav-links">
          <a href="index.html" ${isActive('index.html') ? 'class="active"' : ''}>Home</a>
          <a href="platform.html" ${isActive('platform.html') ? 'class="active"' : ''}>Platform</a>
          <a href="use-cases.html" ${isActive('use-cases.html') ? 'class="active"' : ''}>Use Cases</a>
          <a href="pricing.html" ${isActive('pricing.html') ? 'class="active"' : ''}>Pricing</a>
          <a href="about.html" ${isActive('about.html') ? 'class="active"' : ''}>About</a>
          <a href="about.html#contact" class="nav-cta">Request Demo</a>
        </div>
        <button class="mobile-menu-btn" aria-label="Toggle menu">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12h18M3 6h18M3 18h18"/>
          </svg>
        </button>
      </div>
    </div>
  `;
  document.body.prepend(nav);
  attachNavEventListeners();
}

function attachNavEventListeners() {
  const mobileBtn = document.querySelector('.mobile-menu-btn');
  if (mobileBtn) {
    mobileBtn.addEventListener('click', toggleMobileMenu);
  }
}

function toggleMobileMenu() {
  const nav = document.querySelector('.navbar');
  const links = document.querySelector('.nav-links');
  const btn = document.querySelector('.mobile-menu-btn');

  if (!links) return;

  links.classList.toggle('open');
  btn.classList.toggle('active');
}

/* ========== FOOTER ========== */
function renderFooter() {
  const footer = document.createElement('footer');
  footer.className = 'footer';
  const currentYear = new Date().getFullYear();

  footer.innerHTML = `
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand">
          <a href="index.html" class="nav-logo">
            ${LOGO_SVG}
            <span>NYX <span class="logo-accent">CORE</span></span>
          </a>
          <p>Sovereign Financial Intelligence for Emerging Markets</p>
          <div class="social-links">
            <a href="https://linkedin.com" target="_blank" rel="noopener" aria-label="LinkedIn">${SOCIAL_ICONS.linkedin}</a>
            <a href="https://github.com" target="_blank" rel="noopener" aria-label="GitHub">${SOCIAL_ICONS.github}</a>
            <a href="https://twitter.com" target="_blank" rel="noopener" aria-label="Twitter">${SOCIAL_ICONS.twitter}</a>
          </div>
        </div>
        <div class="footer-col">
          <h4>Product</h4>
          <a href="platform.html">Platform</a>
          <a href="use-cases.html">Use Cases</a>
          <a href="pricing.html">Pricing</a>
          <a href="https://docs.nyxcore.space" target="_blank">Documentation</a>
        </div>
        <div class="footer-col">
          <h4>Company</h4>
          <a href="about.html">About</a>
          <a href="about.html#contact">Contact</a>
          <a href="#">Careers</a>
          <a href="#">Blog</a>
        </div>
        <div class="footer-col">
          <h4>Legal</h4>
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Security</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; ${currentYear} NYX Core Thinker LLC. All rights reserved.</span>
        <span>Tbilisi, Georgia</span>
      </div>
    </div>
  `;
  document.body.appendChild(footer);
}

/* ========== SCROLL ANIMATIONS ========== */
function initScrollAnimations() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        // Unobserve to prevent re-triggering
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  // Fade up animation
  document.querySelectorAll('.fade-up').forEach((el, index) => {
    el.style.setProperty('--stagger-delay', `${index * 100}ms`);
    observer.observe(el);
  });

  // Fade in animation
  document.querySelectorAll('.fade-in').forEach(el => {
    observer.observe(el);
  });

  // Slide animations
  document.querySelectorAll('.slide-left').forEach((el, index) => {
    el.style.setProperty('--stagger-delay', `${index * 100}ms`);
    observer.observe(el);
  });

  document.querySelectorAll('.slide-right').forEach((el, index) => {
    el.style.setProperty('--stagger-delay', `${index * 100}ms`);
    observer.observe(el);
  });

  // Grid children stagger
  document.querySelectorAll('[data-stagger] > *').forEach((el, index) => {
    el.style.setProperty('--stagger-delay', `${index * 80}ms`);
    observer.observe(el);
  });
}

/* ========== NAVIGATION SCROLL EFFECT ========== */
function initNavScroll() {
  const nav = document.querySelector('.navbar');
  if (!nav) return;

  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      nav.style.background = 'rgba(10, 15, 26, 0.98)';
      nav.style.borderBottom = '1px solid rgba(30, 41, 59, 0.5)';
      nav.style.backdropFilter = 'blur(8px)';
    } else {
      nav.style.background = 'rgba(10, 15, 26, 0.7)';
      nav.style.borderBottom = '1px solid rgba(255, 255, 255, 0.06)';
      nav.style.backdropFilter = 'blur(4px)';
    }
  });
}

/* ========== SMOOTH SCROLL FOR ANCHORS ========== */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href === '#') return;

      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
        // Close mobile menu if open
        const mobileLinks = document.querySelector('.nav-links');
        if (mobileLinks && mobileLinks.classList.contains('open')) {
          toggleMobileMenu();
        }
      }
    });
  });
}

/* ========== FAQ ACCORDION ========== */
function initFaqAccordion() {
  const faqItems = document.querySelectorAll('.faq-item');

  faqItems.forEach(item => {
    const trigger = item.querySelector('.faq-trigger');
    if (!trigger) return;

    trigger.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');

      // Close all other items
      faqItems.forEach(other => {
        if (other !== item) {
          other.classList.remove('open');
          const content = other.querySelector('.faq-content');
          if (content) content.style.maxHeight = '0';
        }
      });

      // Toggle current item
      item.classList.toggle('open');
      const content = item.querySelector('.faq-content');
      if (content) {
        content.style.maxHeight = isOpen ? '0' : content.scrollHeight + 'px';
      }
    });
  });
}

/* ========== COUNTER ANIMATION ========== */
function initCounterAnimation() {
  const counters = document.querySelectorAll('[data-counter]');

  const observerOptions = {
    threshold: 0.5
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !entry.target.dataset.animated) {
        animateCounter(entry.target);
        entry.target.dataset.animated = 'true';
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  counters.forEach(counter => observer.observe(counter));
}

function animateCounter(el) {
  const target = parseInt(el.dataset.counter) || 0;
  const duration = parseInt(el.dataset.duration) || 2000;
  const increment = target / (duration / 16);
  let current = 0;

  const suffix = el.dataset.suffix || '';
  const useCommas = target > 999;

  const timer = setInterval(() => {
    current += increment;
    if (current >= target) {
      el.textContent = useCommas ? target.toLocaleString() : target;
      if (suffix) el.textContent += suffix;
      clearInterval(timer);
    } else {
      const val = Math.floor(current);
      el.textContent = useCommas ? val.toLocaleString() : val;
    }
  }, 16);
}

/* ========== TYPING EFFECT ========== */
function initTypingEffect() {
  const elements = document.querySelectorAll('[data-type-text]');

  elements.forEach(el => {
    const text = el.dataset.typeText;
    const speed = parseInt(el.dataset.typeSpeed) || 50;

    typeWriter(el, text, speed);
  });
}

function typeWriter(el, text, speed) {
  el.textContent = '';
  let index = 0;

  function type() {
    if (index < text.length) {
      el.textContent += text.charAt(index);
      index++;
      setTimeout(type, speed);
    }
  }

  type();
}

/* ========== INITIALIZATION ========== */
document.addEventListener('DOMContentLoaded', () => {
  renderNav();
  renderFooter();
  initScrollAnimations();
  initNavScroll();
  initSmoothScroll();
  initFaqAccordion();
  initCounterAnimation();
  initTypingEffect();
});
