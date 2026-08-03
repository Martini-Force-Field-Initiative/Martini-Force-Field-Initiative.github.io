// Parse an MM/DD/YYYY date string into a Date. Returns an invalid Date if the
// string does not match, so callers can detect malformed input.
function parseDate(dateStr) {
    const [month, day, year] = String(dateStr || '').split('/');
    return new Date(Number(year), Number(month) - 1, Number(day));
}

// Function to format date from MM/DD/YYYY to a more readable format
function formatDate(dateStr) {
    const date = parseDate(dateStr);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Function to create a news card element
function createNewsCard(announcement, isFeatured = false) {
    const card = document.createElement('article');
    card.className = `news-card ${isFeatured ? 'featured' : ''} animate-in`;

    // Create image container and image
    const imageContainer = document.createElement('div');
    imageContainer.className = 'news-image-container';
    
    const img = document.createElement('img');
    // Matches the fallback used by scripts/generate-announcements-metadata.py
    // and the image-placeholder in docs/announcements/index.qmd.
    img.src = announcement.image || '/images/cell1.jpg';
    img.alt = announcement.title;
    img.className = 'news-image';
    imageContainer.appendChild(img);

    card.appendChild(imageContainer);

    // Create content container
    const content = document.createElement('div');
    content.className = 'news-content';

    // Add meta information
    const meta = document.createElement('div');
    meta.className = 'news-meta';
    
    // Ensure proper flexbox layout for featured cards
    if (isFeatured) {
        meta.style.display = 'flex';
        meta.style.alignItems = 'center';
        meta.style.justifyContent = 'space-between';
        meta.style.flexWrap = 'nowrap';
        meta.style.gap = '0.5rem';
        meta.style.width = '100%';
    }
    
    const date = document.createElement('span');
    date.className = 'news-date';
    // Give more space to date in featured cards while maintaining card width
    if (isFeatured) {
        date.style.flexGrow = '0';
        date.style.flexShrink = '1';
        date.style.marginRight = '0.5rem';
        date.style.minWidth = '0';
        date.style.whiteSpace = 'nowrap';
        date.style.overflow = 'hidden';
        date.style.textOverflow = 'ellipsis';
        date.style.maxWidth = '60%';
    }
    date.textContent = formatDate(announcement.date);
    meta.appendChild(date);

    // Add featured badge if it's the featured card
    if (isFeatured) {
        const badge = document.createElement('span');
        badge.className = 'news-badge-inline';
        badge.style.flexShrink = '0';
        badge.style.marginLeft = 'auto';
        badge.textContent = 'Latest';
        meta.appendChild(badge);
    }

    if (announcement.category) {
        const category = document.createElement('span');
        category.className = 'news-category';
        category.textContent = announcement.category;
        meta.appendChild(category);
    }

    content.appendChild(meta);

    // Add title
    const title = document.createElement('h3');
    title.className = 'news-title';
    title.textContent = announcement.title;
    content.appendChild(title);

    // Add excerpt
    const excerpt = document.createElement('p');
    excerpt.className = 'news-excerpt';
    excerpt.textContent = announcement.description;
    content.appendChild(excerpt);

    // Add footer with author and read more link
    const footer = document.createElement('div');
    footer.className = 'news-footer';

    if (announcement.author) {
        const authorDiv = document.createElement('div');
        authorDiv.className = 'news-author';
        
        const authorName = document.createElement('span');
        authorName.innerHTML = `<strong>Author:</strong> ${announcement.author}`;
        
        authorDiv.appendChild(authorName);
        footer.appendChild(authorDiv);
    }

    const readMore = document.createElement('a');
    readMore.href = announcement.url || '#';
    readMore.className = 'news-link';
    readMore.textContent = 'Read More →';
    footer.appendChild(readMore);

    content.appendChild(footer);
    card.appendChild(content);

    return card;
}

// Function to load and display announcements
async function loadAnnouncements() {
    try {
        // Fetch the announcements data
        const response = await fetch('/docs/announcements/posts/_metadata.yml');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const metadata = await response.text();
        
        // Parse the YAML metadata
        const announcements = parseYAML(metadata);
        
        // Sort announcements by date (newest first).
        // Dates are MM/DD/YYYY. Reversing the parts would yield YYYY-DD-MM,
        // which silently mis-orders every post whose day and month differ.
        announcements.sort((a, b) => parseDate(b.date) - parseDate(a.date));

        // Get the news grid container
        const newsGrid = document.querySelector('.news-grid');
        if (!newsGrid) return;

        // Clear existing content
        newsGrid.innerHTML = '';

        // Add the featured announcement first
        if (announcements.length > 0) {
            const featuredCard = createNewsCard(announcements[0], true);
            newsGrid.appendChild(featuredCard);
        }

        // Add the next 3 most recent announcements
        announcements.slice(1, 4).forEach(announcement => {
            const card = createNewsCard(announcement);
            newsGrid.appendChild(card);
        });

        // Add "View All Announcements" button
        const viewAllButton = document.createElement('div');
        viewAllButton.className = 'view-all-container';
        viewAllButton.innerHTML = `
            <a href="/docs/announcements/" class="view-all-button">
                <span>View All Announcements</span>
                <span class="arrow">→</span>
            </a>
        `;
        newsGrid.appendChild(viewAllButton);

        // Initialize animations
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.animate-in').forEach((el) => observer.observe(el));

    } catch (error) {
        console.error('Error loading announcements:', error);
        // Add error handling UI if needed
        const newsGrid = document.querySelector('.news-grid');
        if (newsGrid) {
            newsGrid.innerHTML = '<div class="error-message">Unable to load announcements. Please try again later.</div>';
        }
    }
}

// Simple YAML parser for metadata
// Split "key: value" at the FIRST colon only. Returns null when the line is
// not a key/value pair.
//
// The previous implementation used `line.split(':')[1]`, which truncated any
// value containing a colon, so "New tool: Bentopy" reached the homepage as
// "New tool". Field dispatch used `line.includes('date:')`, which was worse: a
// description mentioning "date:" was stored as the announcement's date,
// because `date:` was tested before `description:`.
function splitKeyValue(line) {
    const trimmed = line.trim().replace(/^-\s+/, '');
    const colon = trimmed.indexOf(':');
    if (colon === -1) return null;

    const key = trimmed.slice(0, colon).trim();
    // A key is a bare identifier. Anything else means this colon belonged to
    // a value rather than starting a field.
    if (!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(key)) return null;

    return [key, unquote(trimmed.slice(colon + 1).trim())];
}

// Strip one layer of matching surrounding quotes, leaving inner quotes intact.
function unquote(value) {
    if (value.length >= 2) {
        const first = value[0];
        if ((first === '"' || first === "'") && value[value.length - 1] === first) {
            return value.slice(1, -1);
        }
    }
    return value;
}

const FEED_FIELDS = new Set([
    'title', 'description', 'date', 'image', 'url',
    'author', 'authorAvatar', 'category'
]);

function parseYAML(yamlText) {
    const announcements = [];
    const lines = yamlText.split('\n');
    let currentAnnouncement = null;
    let inAnnouncements = false;

    for (const line of lines) {
        if (line.trim() === 'announcements:') {
            inAnnouncements = true;
            continue;
        }
        if (!inAnnouncements) continue;

        const pair = splitKeyValue(line);
        if (!pair) continue;
        const [key, value] = pair;

        // Each list item begins with "- title:".
        if (/^\s*-\s/.test(line) && key === 'title') {
            if (currentAnnouncement) {
                announcements.push(currentAnnouncement);
            }
            currentAnnouncement = { title: value, tags: [] };
            continue;
        }

        if (!currentAnnouncement) continue;

        if (key === 'tags') {
            currentAnnouncement.tags = value
                .replace(/[[\]]/g, '')
                .split(',')
                .map(tag => tag.trim())
                .filter(Boolean);
        } else if (FEED_FIELDS.has(key)) {
            currentAnnouncement[key] = value;
        }
    }

    if (currentAnnouncement) {
        announcements.push(currentAnnouncement);
    }

    return announcements;
}

// Load announcements when the page loads
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', loadAnnouncements);
}

// Exported so the CI consumer-contract tests can exercise the *real* parser
// used by the homepage rather than a re-implementation that could drift.
// No-op in the browser.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { parseYAML, formatDate, parseDate, splitKeyValue, unquote };
} 