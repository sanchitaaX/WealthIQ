document.addEventListener("DOMContentLoaded", () => {
    // Auto-fade flash messages after 5 seconds
    const alerts = document.querySelectorAll(".flash-container .alert");
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), transform 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)";
            alert.style.opacity = "0";
            alert.style.transform = "translateX(20px)";
            setTimeout(() => alert.remove(), 400);
        }, 5000);
    });

    // Mobile sidebar toggle
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    const overlay = document.getElementById('sidebarOverlay');

    function openSidebar() {
        if (sidebar) sidebar.classList.add('show');
        if (overlay) overlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('show');
        if (overlay) overlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (toggle) {
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (sidebar && sidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // Close sidebar on link click (mobile)
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992) {
                closeSidebar();
            }
        });
    });

    // Close sidebar on window resize to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 992) {
            closeSidebar();
        }
    });

    // Add subtle entrance animation to metric cards
    const cards = document.querySelectorAll('.metric-card, .card');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.05 });

    cards.forEach((card, i) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(15px)';
        card.style.transition = `opacity 0.5s cubic-bezier(0.25, 0.8, 0.25, 1) ${i * 0.04}s, transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1) ${i * 0.04}s`;
        observer.observe(card);
    });

    // Initialize subtle 3D tilt effects on cards if VanillaTilt is available
    if (typeof VanillaTilt !== "undefined") {
        const tiltCards = document.querySelectorAll(".metric-card, .achievement-card:not(.locked), .challenge-card:not(.completed)");
        VanillaTilt.init(Array.from(tiltCards), {
            max: 5,
            speed: 400,
            glare: true,
            "max-glare": 0.08,
            scale: 1.01,
            transition: true
        });
    }
});
