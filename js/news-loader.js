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

    // Create image element
    const img = document.createElement('img');
    img.src = announcement.image || 'images/default-news.png';
    img.alt = announcement.title;
    img.className = 'news-image';
    card.appendChild(img);

    // Create content container
    const content = document.createElement('div');
    content.className = 'news-content';

    // Add date
    const date = document.createElement('div');
    date.className = 'news-date';
    date.textContent = formatDate(announcement.date);
    content.appendChild(date);

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

    // Add author
    const author = document.createElement('div');
    author.className = 'news-author';
    author.innerHTML = `<i class="fa fa-user"></i> ${announcement.author}`;
    content.appendChild(author);

    // Add read more link
    const readMore = document.createElement('a');
    readMore.href = announcement.url || '#';
    readMore.className = 'read-more';
    readMore.textContent = 'Read More';
    content.appendChild(readMore);

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

        // Add the three most recent announcements
        announcements.slice(0, 3).forEach((announcement, index) => {
            const card = createNewsCard(announcement, index === 0);
            newsGrid.appendChild(card);
        });

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
            } else if (line.includes('tags:')) {
                const tags = line.split(':')[1].trim().replace(/[\[\]]/g, '').split(',').map(tag => tag.trim());
                currentAnnouncement.tags = tags;
            } else if (line.includes('url:')) {
                currentAnnouncement.url = line.split(':')[1].trim().replace(/"/g, '');
            } else if (line.includes('author:')) {
                currentAnnouncement.author = line.split(':')[1].trim().replace(/"/g, '');
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