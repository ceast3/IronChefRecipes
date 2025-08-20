/**
 * Iron Chef Recipe Database - Main JavaScript
 * Handles dynamic functionality, AJAX requests, and user interactions
 */

// Global application object
const IronChefApp = {
    // Configuration
    config: {
        apiEndpoints: {
            themes: '/api/themes',
            stats: '/api/stats',
            dashboardStats: '/api/dashboard-stats'
        },
        searchDelayMs: 300,
        animationDuration: 300
    },
    
    // Get CSRF token from meta tag
    getCSRFToken: function() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : null;
    },
    
    // State management
    state: {
        currentPage: 1,
        searchQuery: '',
        filters: {},
        isLoading: false
    },
    
    // Initialize the application
    init: function() {
        this.setupEventListeners();
        this.initializeComponents();
        this.loadThemes();
        this.loadDashboardStats();
        this.setupAccessibility();
    },
    
    // Set up global event listeners
    setupEventListeners: function() {
        // Form submissions with loading states
        document.addEventListener('submit', this.handleFormSubmit.bind(this));
        
        // Search functionality
        const searchInputs = document.querySelectorAll('input[type="search"], input[name="q"]');
        searchInputs.forEach(input => {
            input.addEventListener('input', this.debounce(this.handleSearchInput.bind(this), this.config.searchDelayMs));
        });
        
        // Navigation enhancements
        this.setupNavigationHighlight();
        
        // Responsive menu handling
        this.setupMobileMenu();
        
        // Progress tracking for recipes
        this.setupProgressTracking();
        
        // Keyboard shortcuts
        this.setupKeyboardShortcuts();
    },
    
    // Initialize components
    initializeComponents: function() {
        // Initialize tooltips if Bootstrap is available
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
        
        // Initialize card animations
        this.initializeCardAnimations();
        
        // Initialize lazy loading for images
        this.initializeLazyLoading();
        
        // Initialize infinite scroll if needed
        this.initializeInfiniteScroll();
    },
    
    // Handle form submissions with loading states
    handleFormSubmit: function(event) {
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');
        
        if (submitButton) {
            // Add loading state
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading...';
            submitButton.disabled = true;
            submitButton.classList.add('loading');
            
            // Remove loading state after a timeout (in case of errors)
            setTimeout(() => {
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
                submitButton.classList.remove('loading');
            }, 10000);
        }
    },
    
    // Handle search input with debouncing
    handleSearchInput: function(event) {
        const query = event.target.value.trim();
        this.state.searchQuery = query;
        
        // Add visual feedback
        const form = event.target.closest('form');
        if (form) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton && query.length > 2) {
                submitButton.classList.add('btn-outline-success');
                submitButton.classList.remove('btn-primary');
            } else if (submitButton) {
                submitButton.classList.remove('btn-outline-success');
                submitButton.classList.add('btn-primary');
            }
        }
    },
    
    // Setup navigation highlighting
    setupNavigationHighlight: function() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
        
        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href && currentPath.startsWith(href) && href !== '/') {
                link.classList.add('active');
            } else if (href === '/' && currentPath === '/') {
                link.classList.add('active');
            }
        });
    },
    
    // Setup mobile menu functionality
    setupMobileMenu: function() {
        const navbarToggler = document.querySelector('.navbar-toggler');
        const navbarCollapse = document.querySelector('.navbar-collapse');
        
        if (navbarToggler && navbarCollapse) {
            // Close menu when clicking outside
            document.addEventListener('click', (event) => {
                if (!navbarCollapse.contains(event.target) && 
                    !navbarToggler.contains(event.target) && 
                    navbarCollapse.classList.contains('show')) {
                    navbarToggler.click();
                }
            });
            
            // Close menu when clicking on nav links (mobile)
            const navLinks = navbarCollapse.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    if (navbarCollapse.classList.contains('show')) {
                        navbarToggler.click();
                    }
                });
            });
        }
    },
    
    // Setup progress tracking for recipes
    setupProgressTracking: function() {
        const checkboxes = document.querySelectorAll('.ingredient-check, .step-check');
        
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (event) => {
                this.updateProgressTracking();
                this.saveProgress();
                this.animateCheckbox(event.target);
            });
        });
        
        // Load saved progress
        this.loadProgress();
    },
    
    // Update progress tracking display
    updateProgressTracking: function() {
        const totalChecks = document.querySelectorAll('.ingredient-check, .step-check').length;
        const completedChecks = document.querySelectorAll('.ingredient-check:checked, .step-check:checked').length;
        
        const progressCard = document.getElementById('progressCard');
        const progressText = document.getElementById('progressText');
        
        if (progressCard && progressText) {
            if (completedChecks > 0) {
                progressCard.style.display = 'block';
                progressText.textContent = `${completedChecks}/${totalChecks} completed`;
                
                // Add completion animation
                if (completedChecks === totalChecks) {
                    this.showCompletionAnimation();
                }
            } else {
                progressCard.style.display = 'none';
            }
        }
    },
    
    // Animate checkbox changes
    animateCheckbox: function(checkbox) {
        const item = checkbox.closest('.ingredient-item, .instruction-item');
        if (item) {
            item.style.transform = 'scale(0.98)';
            item.style.transition = 'transform 0.1s ease';
            
            setTimeout(() => {
                item.style.transform = 'scale(1)';
            }, 100);
        }
    },
    
    // Show completion animation
    showCompletionAnimation: function() {
        const progressCard = document.getElementById('progressCard');
        if (progressCard) {
            progressCard.classList.add('border-success');
            progressCard.style.animation = 'pulse 0.5s ease-in-out';
            
            setTimeout(() => {
                progressCard.classList.remove('border-success');
                progressCard.style.animation = '';
            }, 1000);
        }
    },
    
    // Save progress to localStorage
    saveProgress: function() {
        const recipeId = this.getRecipeId();
        if (recipeId) {
            const progress = {
                ingredients: Array.from(document.querySelectorAll('.ingredient-check')).map(cb => cb.checked),
                steps: Array.from(document.querySelectorAll('.step-check')).map(cb => cb.checked),
                timestamp: Date.now()
            };
            localStorage.setItem(`recipe_progress_${recipeId}`, JSON.stringify(progress));
        }
    },
    
    // Load progress from localStorage
    loadProgress: function() {
        const recipeId = this.getRecipeId();
        if (recipeId) {
            try {
                const saved = localStorage.getItem(`recipe_progress_${recipeId}`);
                if (saved) {
                    const progress = JSON.parse(saved);
                    
                    // Only load if not too old (7 days)
                    if (Date.now() - progress.timestamp < 7 * 24 * 60 * 60 * 1000) {
                        progress.ingredients.forEach((checked, index) => {
                            const checkbox = document.querySelectorAll('.ingredient-check')[index];
                            if (checkbox) {
                                checkbox.checked = checked;
                                checkbox.dispatchEvent(new Event('change'));
                            }
                        });
                        
                        progress.steps.forEach((checked, index) => {
                            const checkbox = document.querySelectorAll('.step-check')[index];
                            if (checkbox) {
                                checkbox.checked = checked;
                                checkbox.dispatchEvent(new Event('change'));
                            }
                        });
                    }
                }
            } catch (e) {
                console.log('Could not load saved progress:', e);
            }
        }
    },
    
    // Get recipe ID from current page
    getRecipeId: function() {
        const match = window.location.pathname.match(/\/recipe\/(\d+)/);
        return match ? match[1] : null;
    },
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts: function() {
        document.addEventListener('keydown', (event) => {
            // Ctrl/Cmd + K for search
            if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
                event.preventDefault();
                const searchInput = document.querySelector('input[name="q"], input[type="search"]');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
            
            // Escape to close modals/menus
            if (event.key === 'Escape') {
                const navbarCollapse = document.querySelector('.navbar-collapse.show');
                if (navbarCollapse) {
                    document.querySelector('.navbar-toggler').click();
                }
            }
        });
    },
    
    // Initialize card animations
    initializeCardAnimations: function() {
        const cards = document.querySelectorAll('.card');
        
        // Intersection Observer for scroll animations
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '50px'
            });
            
            cards.forEach(card => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                observer.observe(card);
            });
        }
    },
    
    // Initialize lazy loading for images
    initializeLazyLoading: function() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.classList.add('loaded');
                            imageObserver.unobserve(img);
                        }
                    }
                });
            });
            
            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    },
    
    // Initialize infinite scroll (if needed)
    initializeInfiniteScroll: function() {
        const pagination = document.querySelector('.pagination');
        const nextLink = document.querySelector('.pagination .page-item:last-child a');
        
        if (pagination && nextLink && nextLink.href && !nextLink.href.includes('#')) {
            let isLoading = false;
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting && !isLoading) {
                        isLoading = true;
                        // Could implement auto-loading here if desired
                    }
                });
            });
            
            observer.observe(pagination);
        }
    },
    
    // Enhanced fetch with CSRF support
    fetchWithCSRF: function(url, options = {}) {
        const csrfToken = this.getCSRFToken();
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken && { 'X-CSRFToken': csrfToken })
            }
        };
        
        return fetch(url, { ...defaultOptions, ...options });
    },
    
    // Load themes via AJAX
    loadThemes: function() {
        const themeSelects = document.querySelectorAll('select[name="theme"]');
        
        if (themeSelects.length > 0) {
            this.fetchWithCSRF(this.config.apiEndpoints.themes)
                .then(response => response.json())
                .then(data => {
                    themeSelects.forEach(select => {
                        // Keep current selection
                        const currentValue = select.value;
                        
                        // Clear existing options except "All Themes"
                        while (select.options.length > 1) {
                            select.removeChild(select.lastChild);
                        }
                        
                        // Add new options
                        data.themes.forEach(theme => {
                            const option = document.createElement('option');
                            option.value = theme;
                            option.textContent = theme;
                            if (theme === currentValue) {
                                option.selected = true;
                            }
                            select.appendChild(option);
                        });
                    });
                })
                .catch(error => {
                    console.log('Could not load themes:', error);
                });
        }
    },
    
    // Load dashboard statistics
    loadDashboardStats: function() {
        const statsContainer = document.querySelector('#dashboard-stats');
        if (statsContainer) {
            this.fetchWithCSRF(this.config.apiEndpoints.dashboardStats)
                .then(response => response.json())
                .then(data => {
                    this.updateDashboardStats(data);
                })
                .catch(error => {
                    console.log('Could not load dashboard stats:', error);
                });
        }
    },
    
    // Update dashboard statistics display
    updateDashboardStats: function(stats) {
        // Update episode count
        const episodeCount = document.querySelector('#episode-count');
        if (episodeCount) episodeCount.textContent = stats.episodes || 0;
        
        // Update recipe count
        const recipeCount = document.querySelector('#recipe-count');
        if (recipeCount) recipeCount.textContent = stats.recipes || 0;
        
        // Update dish count
        const dishCount = document.querySelector('#dish-count');
        if (dishCount) dishCount.textContent = stats.dishes || 0;
        
        // Update recipes generated today
        const recipesToday = document.querySelector('#recipes-today');
        if (recipesToday) recipesToday.textContent = stats.recipes_today || 0;
    },
    
    // Setup accessibility features
    setupAccessibility: function() {
        // Add skip link
        this.addSkipLink();
        
        // Improve focus management
        this.improveFocusManagement();
        
        // Add ARIA labels where needed
        this.addAriaLabels();
        
        // Setup reduced motion preferences
        this.setupReducedMotion();
    },
    
    // Add skip link for keyboard navigation
    addSkipLink: function() {
        const skipLink = document.createElement('a');
        skipLink.href = '#main-content';
        skipLink.textContent = 'Skip to main content';
        skipLink.className = 'sr-only sr-only-focusable btn btn-primary';
        skipLink.style.position = 'fixed';
        skipLink.style.top = '10px';
        skipLink.style.left = '10px';
        skipLink.style.zIndex = '9999';
        
        skipLink.addEventListener('focus', function() {
            this.classList.remove('sr-only');
        });
        
        skipLink.addEventListener('blur', function() {
            this.classList.add('sr-only');
        });
        
        document.body.insertBefore(skipLink, document.body.firstChild);
        
        // Add main content ID if not present
        const main = document.querySelector('main');
        if (main && !main.id) {
            main.id = 'main-content';
        }
    },
    
    // Improve focus management
    improveFocusManagement: function() {
        // Focus management for dynamic content
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', (event) => {
                // Focus management after form submission
                setTimeout(() => {
                    const errorAlert = document.querySelector('.alert-danger');
                    const successAlert = document.querySelector('.alert-success');
                    
                    if (errorAlert) {
                        errorAlert.focus();
                    } else if (successAlert) {
                        successAlert.focus();
                    }
                }, 100);
            });
        });
    },
    
    // Add ARIA labels where needed
    addAriaLabels: function() {
        // Add ARIA labels to search forms
        const searchInputs = document.querySelectorAll('input[type="search"], input[name="q"]');
        searchInputs.forEach(input => {
            if (!input.getAttribute('aria-label')) {
                input.setAttribute('aria-label', 'Search episodes, dishes, and recipes');
            }
        });
        
        // Add ARIA labels to pagination
        const paginationLinks = document.querySelectorAll('.pagination a');
        paginationLinks.forEach(link => {
            const text = link.textContent.trim();
            if (text === 'Previous') {
                link.setAttribute('aria-label', 'Go to previous page');
            } else if (text === 'Next') {
                link.setAttribute('aria-label', 'Go to next page');
            } else if (!isNaN(text)) {
                link.setAttribute('aria-label', `Go to page ${text}`);
            }
        });
    },
    
    // Setup reduced motion preferences
    setupReducedMotion: function() {
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            // Disable animations for users who prefer reduced motion
            const style = document.createElement('style');
            style.textContent = `
                *, *::before, *::after {
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }
            `;
            document.head.appendChild(style);
        }
    },
    
    // Utility function for debouncing
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Utility function for throttling
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    IronChefApp.init();
});

// Export for use in other scripts
window.IronChefApp = IronChefApp;