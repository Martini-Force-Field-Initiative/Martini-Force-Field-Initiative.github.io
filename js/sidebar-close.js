// Simple Sidebar-Navbar Conflict Handler
// Ensures sidebar and navbar menu don't appear at the same time

document.addEventListener('DOMContentLoaded', function() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('#navbarCollapse');
    const sidebar = document.querySelector('#quarto-sidebar');
    const sidebarToggler = document.querySelector('.quarto-btn-toggle');
    const sidebarGlass = document.querySelector('#quarto-sidebar-glass');
    
    // Function to close sidebar properly while preserving its ability to reopen
    function closeSidebar() {
        if (!sidebar) return;
        
        console.log('Closing sidebar...');
        
        // Method 1: Use Bootstrap collapse (preferred)
        if (typeof bootstrap !== 'undefined' && bootstrap.Collapse) {
            try {
                const bsCollapse = bootstrap.Collapse.getOrCreateInstance(sidebar);
                bsCollapse.hide();
                console.log('Used Bootstrap collapse');
            } catch (e) {
                console.warn('Bootstrap method failed:', e);
                // Fallback to manual method
                manualClose();
            }
        } else {
            manualClose();
        }
        
        // Always clean up the glass overlay manually
        cleanupOverlay();
    }
    
    // Manual close method (less aggressive)
    function manualClose() {
        sidebar.classList.remove('show', 'showing');
        sidebar.classList.add('collapse');
        // Don't set display: none - let Bootstrap handle it
        console.log('Used manual close');
    }
    
    // Clean up overlay elements
    function cleanupOverlay() {
        // Remove the gray overlay/glass
        if (sidebarGlass) {
            sidebarGlass.style.display = 'none';
            sidebarGlass.classList.remove('show');
        }
        
        // Clean up any modal-like states on body
        document.body.classList.remove('sidebar-open', 'modal-open');
        document.body.style.overflow = '';
        
        // Remove any backdrop elements that might be lingering
        const backdrops = document.querySelectorAll('.modal-backdrop, .sidebar-backdrop');
        backdrops.forEach(backdrop => backdrop.remove());
        
        console.log('Overlay cleaned up');
    }
    
    // Simple function to hide navbar menu
    function hideNavbar() {
        if (!navbarCollapse || !navbarCollapse.classList.contains('show')) return;
        
        console.log('Closing navbar...');
        
        // Use Bootstrap collapse if available
        if (typeof bootstrap !== 'undefined' && bootstrap.Collapse) {
            try {
                const bsCollapse = bootstrap.Collapse.getOrCreateInstance(navbarCollapse);
                bsCollapse.hide();
                console.log('Navbar closed with Bootstrap');
                return;
            } catch (e) {
                console.warn('Bootstrap navbar close failed:', e);
            }
        }
        
        // Manual fallback
        navbarCollapse.classList.remove('show');
        console.log('Navbar closed manually');
    }
    
    // When navbar toggle is clicked, close sidebar
    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            console.log('Navbar toggle clicked');
            setTimeout(closeSidebar, 50);
        });
    }
    
    // When sidebar toggle is clicked, hide navbar
    if (sidebarToggler) {
        sidebarToggler.addEventListener('click', function() {
            console.log('Sidebar toggle clicked');
            setTimeout(hideNavbar, 50);
        });
    }
    
    // Also close sidebar when clicking on the glass/overlay
    if (sidebarGlass) {
        sidebarGlass.addEventListener('click', function() {
            console.log('Sidebar glass clicked');
            closeSidebar();
        });
    }
    
    console.log('Sidebar-navbar handler initialized');
});
