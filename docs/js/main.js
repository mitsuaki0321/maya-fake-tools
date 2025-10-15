/**
 * FakeTools Documentation JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for TOC links
    setupSmoothScrolling();

    // Highlight active TOC link on scroll
    setupTOCHighlight();

    // Add copy button to code blocks
    setupCodeCopyButtons();

    // Make tool cards clickable
    setupToolCardClicks();
});

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
                const headerOffset = 80; // Adjust for sticky header
                const elementPosition = targetElement.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

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
        rootMargin: '-80px 0px -80% 0px'
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
