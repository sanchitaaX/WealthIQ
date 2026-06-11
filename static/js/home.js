document.addEventListener("DOMContentLoaded", () => {
    // Render Top Categories chart if data exists
    if (typeof categoryDataRaw !== 'undefined' && categoryDataRaw.length > 0) {
        const ctx = document.getElementById('homeCategoryChart');
        if (ctx) {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: categoryDataRaw.map(d => d.category),
                    datasets: [{
                        data: categoryDataRaw.map(d => d.total),
                        backgroundColor: [
                            '#2C5CFF', '#C9940E', '#1A8C52', '#525252', '#8C8C8C', '#E8E8E4', '#F0EFEC'
                        ],
                        borderWidth: 0,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { 
                            position: 'right',
                            labels: {
                                font: { family: "'Inter', sans-serif" },
                                color: '#525252'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            titleColor: '#171717',
                            bodyColor: '#525252',
                            borderColor: '#E8E8E4',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 4,
                            usePointStyle: true,
                            cornerRadius: 8
                        }
                    },
                    cutout: '75%'
                }
            });
        }
    }
});
