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
                            '#5235EF', // Primary Indigo
                            '#8771FF', // Lavender/Light Purple
                            '#FF9F1C', // Accent Gold
                            '#10B981', // Emerald Green
                            '#EF4444', // Coral Red
                            '#3B82F6', // Blue
                            '#64748B'  // Slate
                        ],
                        borderWidth: 2,
                        borderColor: '#FFFFFF',
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
                                font: { 
                                    family: "'Inter', sans-serif",
                                    weight: '600',
                                    size: 11
                                },
                                color: '#5C5E66',
                                usePointStyle: true,
                                boxWidth: 8,
                                padding: 15
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(255, 255, 255, 0.98)',
                            titleColor: '#101011',
                            titleFont: { family: "'Inter', sans-serif", weight: '700' },
                            bodyColor: '#5C5E66',
                            bodyFont: { family: "'Inter', sans-serif" },
                            borderColor: '#E2E5EC',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            usePointStyle: true,
                            cornerRadius: 12,
                            shadowColor: 'rgba(16, 16, 17, 0.08)',
                            shadowBlur: 10
                        }
                    },
                    cutout: '72%'
                }
            });
        }
    }
});
