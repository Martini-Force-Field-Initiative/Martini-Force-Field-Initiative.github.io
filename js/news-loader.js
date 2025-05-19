// Function to format date from MM/DD/YYYY to a more readable format
function formatDate(dateStr) {
    const [month, day, year] = dateStr.split('/');
    const date = new Date(year, month - 1, day);
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
    img.src = announcement.image || 'images/default-news.jpg';
    img.alt = announcement.title;
    img.className = 'news-image';
    imageContainer.appendChild(img);

    // Add featured badge if it's the featured card
    if (isFeatured) {
        const badge = document.createElement('div');
        badge.className = 'news-badge';
        badge.textContent = 'Latest';
        imageContainer.appendChild(badge);
    }

    card.appendChild(imageContainer);

    // Create content container
    const content = document.createElement('div');
    content.className = 'news-content';

    // Add meta information
    const meta = document.createElement('div');
    meta.className = 'news-meta';
    
    const date = document.createElement('span');
    date.className = 'news-date';
    date.textContent = formatDate(announcement.date);
    meta.appendChild(date);

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
        
        // Sort announcements by date (newest first)
        announcements.sort((a, b) => {
            const dateA = new Date(a.date.split('/').reverse().join('-'));
            const dateB = new Date(b.date.split('/').reverse().join('-'));
            return dateB - dateA;
        });

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

        // Add the next 2 most recent announcements
        announcements.slice(1, 3).forEach(announcement => {
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
function parseYAML(yamlText) {
    // This is a simple implementation - you might want to use a proper YAML parser
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

        if (line.trim().startsWith('- title:')) {
            if (currentAnnouncement) {
                announcements.push(currentAnnouncement);
            }
            currentAnnouncement = {
                title: line.split(':')[1].trim().replace(/"/g, ''),
                tags: []
            };
        } else if (currentAnnouncement) {
            if (line.includes('date:')) {
                currentAnnouncement.date = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('description:')) {
                currentAnnouncement.description = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('image:')) {
                currentAnnouncement.image = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('category:')) {
                currentAnnouncement.category = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('tags:')) {
                const tags = line.split(':')[1].trim().replace(/[\[\]]/g, '').split(',').map(tag => tag.trim());
                currentAnnouncement.tags = tags;
            } else if (line.includes('url:')) {
                currentAnnouncement.url = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('author:')) {
                currentAnnouncement.author = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('authorAvatar:')) {
                currentAnnouncement.authorAvatar = line.split(':')[1].trim().replace(/"/g, '');
            }
        }
    }

    if (currentAnnouncement) {
        announcements.push(currentAnnouncement);
    }

    return announcements;
}

// Load announcements when the page loads
document.addEventListener('DOMContentLoaded', loadAnnouncements); 