document.addEventListener("DOMContentLoaded", () => {
    fetchAndRenderAnalytics();
});

async function fetchAndRenderAnalytics() {
    try {
        const [monthlyRes, categoryRes, weeklyRes, forecastRes, healthRes] = await Promise.all([
            fetch('/api/analytics/monthly-trend'),
            fetch('/api/analytics/category-breakdown'),
            fetch('/api/analytics/weekly-comparison'),
            fetch('/api/analytics/forecast'),
            fetch('/api/analytics/financial-health')
        ]);

        const monthlyData = await monthlyRes.json();
        const categoryData = await categoryRes.json();
        const weeklyData = await weeklyRes.json();
        const forecastData = await forecastRes.json();
        const healthData = await healthRes.json();

        renderMonthlyTrend(monthlyData);
        renderCategoryPie(categoryData);
        renderWeeklyComparison(weeklyData);
        renderForecast(forecastData);
        renderHealthSuggestions(healthData);

    } catch (e) {
        console.error("Error fetching analytics data:", e);
    }
}

// Chart Global Settings
const commonTooltip = {
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
    cornerRadius: 12
};

function renderMonthlyTrend(data) {
    const ctx = document.getElementById('monthlyTrendChart');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.month),
            datasets: [{
                label: 'Spending (₹)',
                data: data.map(d => d.amount),
                borderColor: '#5235EF',
                backgroundColor: 'rgba(82, 53, 239, 0.06)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#5235EF',
                pointBorderColor: '#FFFFFF',
                pointHoverBackgroundColor: '#FFFFFF',
                pointHoverBorderColor: '#5235EF',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { display: false },
                tooltip: commonTooltip
            },
            scales: {
                x: { 
                    grid: { display: false },
                    ticks: { color: '#5C5E66', font: { family: "'Inter', sans-serif" } }
                },
                y: { 
                    grid: { color: '#EEF1F6' },
                    border: { display: false },
                    ticks: { color: '#5C5E66', font: { family: "'Inter', sans-serif" } }
                }
            }
        }
    });
}

function renderCategoryPie(data) {
    const ctx = document.getElementById('categoryPieChart');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.map(d => d.category),
            datasets: [{
                data: data.map(d => d.total),
                backgroundColor: [
                    '#5235EF', '#8771FF', '#FF9F1C', '#10B981', '#EF4444', '#3B82F6', '#64748B'
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
                        font: { family: "'Inter', sans-serif", weight: '600', size: 11 },
                        color: '#5C5E66',
                        usePointStyle: true,
                        boxWidth: 8,
                        padding: 15
                    }
                },
                tooltip: commonTooltip
            }
        }
    });
}

function renderWeeklyComparison(data) {
    const ctx = document.getElementById('weeklyComparisonChart');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'This Week',
                    data: data.this_week,
                    backgroundColor: '#5235EF',
                    borderRadius: 8
                },
                {
                    label: 'Last Week',
                    data: data.last_week,
                    backgroundColor: '#EEF1F6',
                    borderRadius: 8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: commonTooltip,
                legend: {
                    labels: { color: '#5C5E66', font: { family: "'Inter', sans-serif", weight: '600', size: 11 }, usePointStyle: true, boxWidth: 8 }
                }
            },
            scales: {
                x: { 
                    grid: { display: false },
                    ticks: { color: '#5C5E66', font: { family: "'Inter', sans-serif" } }
                },
                y: { 
                    grid: { color: '#EEF1F6' },
                    border: { display: false },
                    ticks: { color: '#5C5E66', font: { family: "'Inter', sans-serif" } }
                }
            }
        }
    });
}

function renderForecast(data) {
    const container = document.getElementById('forecast-container');
    if (!container) return;
    
    let html = `
        <div class="col-sm-6">
            <div class="forecast-card ${data.budget_overrun ? 'warning' : ''}" style="background: var(--surface); border-radius: var(--radius-md); padding: 24px; border: 1px solid ${data.budget_overrun ? 'var(--danger)' : 'var(--border)'};">
                <h4 style="font-size: 0.75rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;">Predicted Spending</h4>
                <div class="val" style="font-size: 1.5rem; font-weight: 800; color: var(--text);">₹${data.predicted_spending.toLocaleString()}</div>
                <p style="font-size: 0.8rem; margin-top:0.5rem; margin-bottom: 0; color: var(--text-secondary);">Based on last 3 months average</p>
            </div>
        </div>
        <div class="col-sm-6">
            <div class="forecast-card" style="background: var(--surface); border-radius: var(--radius-md); padding: 24px; border: 1px solid var(--border);">
                <h4 style="font-size: 0.75rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;">Predicted Savings</h4>
                <div class="val" style="font-size: 1.5rem; font-weight: 800; color: var(--text);">₹${data.predicted_savings.toLocaleString()}</div>
                <p style="font-size: 0.8rem; margin-top:0.5rem; margin-bottom: 0; color: var(--text-secondary);">Assuming income of ₹${data.income.toLocaleString()}</p>
            </div>
        </div>
    `;
    container.innerHTML = html;
}

function renderHealthSuggestions(data) {
    const container = document.getElementById('health-suggestions');
    if (!container) return;
    
    if (data.suggestions && data.suggestions.length > 0) {
        let html = '<ul style="margin-left: 1.5rem; margin-bottom: 0; padding-left: 0; list-style-type: disc; color: var(--text-secondary);">';
        data.suggestions.forEach(s => {
            html += `<li style="margin-bottom: 0.5rem; line-height: 1.4; font-size: 0.9rem;">${s}</li>`;
        });
        html += '</ul>';
        container.innerHTML = html;
    } else {
        container.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.9rem; opacity: 0.8;">No recommendations currently. You are doing great!</span>';
    }
}
