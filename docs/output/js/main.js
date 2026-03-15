/**
 * FakeTools Documentation JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Position breadcrumb bar below sticky header
    setupBreadcrumbBar();

    // Smooth scrolling for TOC links
    setupSmoothScrolling();

    // Highlight active TOC link on scroll
    setupTOCHighlight();

    // Add copy button to code blocks
    setupCodeCopyButtons();

    // Add language labels to code blocks
    setupCodeLanguageLabels();

    // Make tool cards clickable
    setupToolCardClicks();

    // Back to top button
    setupBackToTop();

    // Heading anchor links
    setupHeadingAnchors();

    // Image lightbox
    setupLightbox();

    // Full-text search
    setupSearch();
});

/**
 * Get total height of sticky bars (header + breadcrumb) for scroll offset
 */
function getStickyOffset() {
    let offset = 0;
    const header = document.querySelector('.site-header');
    if (header) offset += header.offsetHeight;
    const breadcrumbBar = document.querySelector('.breadcrumb-bar');
    if (breadcrumbBar) offset += breadcrumbBar.offsetHeight;
    return offset;
}

/**
 * Position breadcrumb bar below the sticky header
 */
function setupBreadcrumbBar() {
    const header = document.querySelector('.site-header');
    const breadcrumbBar = document.querySelector('.breadcrumb-bar');
    if (!header || !breadcrumbBar) return;

    function updatePosition() {
        breadcrumbBar.style.top = header.offsetHeight + 'px';
    }

    updatePosition();
    window.addEventListener('resize', updatePosition);
}

/**
 * Setup smooth scrolling for anchor links
 */
function setupSmoothScrolling() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);

            if (targetElement) {
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - getStickyOffset();

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Highlight active TOC link based on scroll position
 */
function setupTOCHighlight() {
    const tocLinks = document.querySelectorAll('.toc-wrapper a');

    if (tocLinks.length === 0) return;

    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            const id = entry.target.getAttribute('id');
            const tocLink = document.querySelector(`.toc-wrapper a[href="#${id}"]`);

            if (tocLink) {
                if (entry.isIntersecting) {
                    // Remove active class from all links
                    tocLinks.forEach(link => link.classList.remove('active'));
                    // Add active class to current link
                    tocLink.classList.add('active');
                }
            }
        });
    }, {
        rootMargin: `-${getStickyOffset()}px 0px -80% 0px`
    });

    // Observe all headings that have IDs
    document.querySelectorAll('h2[id], h3[id], h4[id]').forEach(heading => {
        observer.observe(heading);
    });
}

/**
 * Add copy buttons to code blocks
 */
function setupCodeCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code');

    codeBlocks.forEach(codeBlock => {
        const pre = codeBlock.parentElement;

        // Create copy button
        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.textContent = 'Copy';
        button.setAttribute('aria-label', 'Copy code to clipboard');

        // Add click handler
        button.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(codeBlock.textContent);
                button.textContent = 'Copied!';
                button.classList.add('copied');

                setTimeout(() => {
                    button.textContent = 'Copy';
                    button.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy code:', err);
                button.textContent = 'Error';
            }
        });

        // Add button to pre element
        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}

/**
 * Make tool cards clickable
 */
function setupToolCardClicks() {
    const toolCards = document.querySelectorAll('.tool-card.has-doc');

    toolCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on a link directly
            if (e.target.tagName === 'A') {
                return;
            }

            // Find the link inside the card
            const link = this.querySelector('h3 a');
            if (link) {
                link.click();
            }
        });
    });
}

// Add CSS for copy button dynamically
const style = document.createElement('style');
style.textContent = `
    .copy-code-btn {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        padding: 0.25rem 0.75rem;
        background-color: var(--bg-tertiary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
        opacity: 0.7;
    }

    .copy-code-btn:hover {
        opacity: 1;
        background-color: var(--accent-primary);
        color: #fff;
    }

    .copy-code-btn.copied {
        background-color: #98c379;
        color: #fff;
    }

    .toc-wrapper a.active {
        color: var(--accent-primary);
        font-weight: 600;
    }
`;
document.head.appendChild(style);

/**
 * Back to top floating button
 */
function setupBackToTop() {
    const button = document.createElement('button');
    button.className = 'back-to-top';
    button.setAttribute('aria-label', 'Back to top');
    button.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 12 10 7 15 12"/></svg>';
    document.body.appendChild(button);

    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                button.classList.toggle('visible', window.scrollY > 300);
                ticking = false;
            });
            ticking = true;
        }
    });

    button.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

/**
 * Add anchor links to headings for URL sharing
 */
function setupHeadingAnchors() {
    const headings = document.querySelectorAll('.main-content h2[id], .main-content h3[id]');

    headings.forEach(heading => {
        const anchor = document.createElement('a');
        anchor.className = 'heading-anchor';
        anchor.href = '#' + heading.id;
        anchor.textContent = '#';
        anchor.setAttribute('aria-label', 'Link to this section');

        anchor.addEventListener('click', async (e) => {
            e.preventDefault();
            const url = window.location.href.split('#')[0] + '#' + heading.id;
            try {
                await navigator.clipboard.writeText(url);
            } catch (err) {
                // Fallback: just navigate
            }
            const elementPosition = heading.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - getStickyOffset();
            window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
            history.replaceState(null, '', '#' + heading.id);
        });

        heading.appendChild(anchor);
    });
}

/**
 * Add language labels to code blocks
 */
function setupCodeLanguageLabels() {
    const langMap = {
        python: 'Python',
        mel: 'MEL',
        bash: 'Bash',
        sh: 'Shell',
        json: 'JSON',
        yaml: 'YAML',
        javascript: 'JavaScript',
        js: 'JavaScript',
        html: 'HTML',
        css: 'CSS',
        markdown: 'Markdown',
    };

    document.querySelectorAll('pre[class]').forEach(pre => {
        const classes = Array.from(pre.classList);
        for (const cls of classes) {
            const langName = langMap[cls.toLowerCase()];
            if (langName) {
                const label = document.createElement('span');
                label.className = 'code-lang-label';
                label.textContent = langName;
                pre.classList.add('has-lang-label');
                pre.insertBefore(label, pre.firstChild);
                break;
            }
        }
    });
}

/**
 * Image lightbox for non-SVG images
 */
function setupLightbox() {
    const images = Array.from(
        document.querySelectorAll('.main-content img:not([src$=".svg"])')
    );
    if (images.length === 0) return;

    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML =
        '<button class="lightbox-close" aria-label="Close">&times;</button>' +
        '<button class="lightbox-nav lightbox-prev" aria-label="Previous">&#8249;</button>' +
        '<img class="lightbox-image" src="" alt="">' +
        '<button class="lightbox-nav lightbox-next" aria-label="Next">&#8250;</button>' +
        '<div class="lightbox-counter"></div>';
    document.body.appendChild(overlay);

    const lbImage = overlay.querySelector('.lightbox-image');
    const lbCounter = overlay.querySelector('.lightbox-counter');
    const lbPrev = overlay.querySelector('.lightbox-prev');
    const lbNext = overlay.querySelector('.lightbox-next');
    let currentIndex = 0;

    function openLightbox(index) {
        currentIndex = index;
        updateLightbox();
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', handleLightboxKey);
    }

    function closeLightbox() {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
        document.removeEventListener('keydown', handleLightboxKey);
    }

    function updateLightbox() {
        lbImage.src = images[currentIndex].src;
        lbImage.alt = images[currentIndex].alt || '';
        lbCounter.textContent = (currentIndex + 1) + ' / ' + images.length;
        lbPrev.style.visibility = images.length > 1 ? 'visible' : 'hidden';
        lbNext.style.visibility = images.length > 1 ? 'visible' : 'hidden';
    }

    function navigate(direction) {
        currentIndex = (currentIndex + direction + images.length) % images.length;
        updateLightbox();
    }

    function handleLightboxKey(e) {
        if (e.key === 'Escape') closeLightbox();
        else if (e.key === 'ArrowLeft') navigate(-1);
        else if (e.key === 'ArrowRight') navigate(1);
    }

    images.forEach((img, i) => {
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', () => openLightbox(i));
    });

    overlay.querySelector('.lightbox-close').addEventListener('click', closeLightbox);
    lbPrev.addEventListener('click', () => navigate(-1));
    lbNext.addEventListener('click', () => navigate(1));
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeLightbox();
    });
}

/**
 * Full-text search with command palette UI
 */
function setupSearch() {
    var searchIndex = window.__SEARCH_INDEX__ || null;
    if (!searchIndex) return;

    var trigger = document.querySelector('.search-trigger-btn');

    // Build overlay DOM
    var overlay = document.createElement('div');
    overlay.className = 'search-overlay';
    var modal = document.createElement('div');
    modal.className = 'search-modal';
    modal.innerHTML =
        '<div class="search-input-wrapper">' +
        '<svg class="search-input-icon" width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="6.5" cy="6.5" r="5"/><line x1="10" y1="10" x2="15" y2="15"/></svg>' +
        '<input class="search-input" type="text" placeholder="Search..." autocomplete="off">' +
        '</div>' +
        '<div class="search-results"></div>';
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    var input = modal.querySelector('.search-input');
    var resultsContainer = modal.querySelector('.search-results');
    var activeIndex = -1;

    // Determine root path from trigger button or page structure
    var rootPath = '';
    var rootLink = document.querySelector('.logo a');
    if (rootLink) {
        var href = rootLink.getAttribute('href');
        var idx = href.lastIndexOf('index');
        if (idx > 0) rootPath = href.substring(0, idx);
    }

    function openSearch() {
        overlay.classList.add('active');
        input.value = '';
        resultsContainer.innerHTML = '';
        activeIndex = -1;
        input.focus();
    }

    function closeSearch() {
        overlay.classList.remove('active');
    }

    function performSearch(query) {
        if (!query.trim()) {
            resultsContainer.innerHTML = '';
            activeIndex = -1;
            return;
        }

        var q = query.toLowerCase();
        var scored = [];

        for (var i = 0; i < searchIndex.length; i++) {
            var entry = searchIndex[i];
            var score = 0;
            var titleLower = entry.title.toLowerCase();
            var descLower = entry.description.toLowerCase();
            var bodyLower = entry.body.toLowerCase();

            if (titleLower === q) score += 100;
            else if (titleLower.indexOf(q) !== -1) score += 50;
            if (descLower.indexOf(q) !== -1) score += 30;

            var bodyMatchPos = bodyLower.indexOf(q);
            if (bodyMatchPos !== -1) score += 10;

            if (score > 0) {
                scored.push({ entry: entry, score: score, bodyMatchPos: bodyMatchPos });
            }
        }

        scored.sort(function(a, b) { return b.score - a.score; });
        var results = scored.slice(0, 10);

        renderResults(results, query);
    }

    function highlightText(text, query) {
        if (!query) return escapeHtml(text);
        var escaped = escapeHtml(text);
        var qLower = query.toLowerCase();
        var tLower = escaped.toLowerCase();
        var idx = tLower.indexOf(qLower);
        if (idx === -1) return escaped;
        var before = escaped.substring(0, idx);
        var match = escaped.substring(idx, idx + query.length);
        var after = escaped.substring(idx + query.length);
        return before + '<mark class="search-highlight">' + match + '</mark>' + after;
    }

    function buildSnippet(body, query, matchPos) {
        if (matchPos === -1 || !body) return '';
        // Extract context around match position
        var start = Math.max(0, matchPos - 30);
        var end = Math.min(body.length, matchPos + query.length + 60);
        var snippet = '';
        if (start > 0) snippet += '...';
        snippet += body.substring(start, end);
        if (end < body.length) snippet += '...';
        return snippet;
    }

    function renderResults(results, query) {
        activeIndex = -1;
        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="search-empty">No results found</div>';
            return;
        }

        var html = '';
        for (var i = 0; i < results.length; i++) {
            var entry = results[i].entry;
            var bodyMatchPos = results[i].bodyMatchPos;
            html += '<a href="' + rootPath + entry.url + '" class="search-result-item" data-index="' + i + '">';
            html += '<div class="search-result-header">';
            html += '<span class="search-result-title">' + highlightText(entry.title, query) + '</span>';
            if (entry.category) {
                html += '<span class="search-result-category">' + escapeHtml(entry.category) + '</span>';
            }
            html += '</div>';
            if (entry.description) {
                html += '<div class="search-result-description">' + highlightText(entry.description, query) + '</div>';
            }
            // Show body snippet if matched in body
            var snippet = buildSnippet(entry.body, query, bodyMatchPos);
            if (snippet) {
                html += '<div class="search-result-snippet">' + highlightText(snippet, query) + '</div>';
            }
            html += '</a>';
        }
        resultsContainer.innerHTML = html;
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function navigateResults(direction) {
        var items = resultsContainer.querySelectorAll('.search-result-item');
        if (items.length === 0) return;

        activeIndex += direction;
        if (activeIndex < 0) activeIndex = items.length - 1;
        if (activeIndex >= items.length) activeIndex = 0;

        items.forEach(function(item, i) {
            item.classList.toggle('active', i === activeIndex);
        });

        items[activeIndex].scrollIntoView({ block: 'nearest' });
    }

    function isInputFocused() {
        var el = document.activeElement;
        return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
    }

    // Event: trigger button click
    if (trigger) {
        trigger.addEventListener('click', openSearch);
    }

    // Event: keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            openSearch();
            return;
        }
        if (e.key === '/' && !isInputFocused()) {
            e.preventDefault();
            openSearch();
            return;
        }
    });

    // Event: input
    input.addEventListener('input', function() {
        performSearch(input.value);
    });

    // Event: keyboard navigation in search
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeSearch();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            navigateResults(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            navigateResults(-1);
        } else if (e.key === 'Enter') {
            var active = resultsContainer.querySelector('.search-result-item.active');
            if (active) {
                active.click();
            }
        }
    });

    // Event: overlay click to close
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeSearch();
    });
}
