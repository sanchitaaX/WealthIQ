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
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    titleColor: '#171717',
    bodyColor: '#525252',
    borderColor: '#E8E8E4',
    borderWidth: 1,
    padding: 12,
    boxPadding: 4,
    usePointStyle: true,
    cornerRadius: 8
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
                borderColor: '#2C5CFF',
                backgroundColor: 'rgba(44, 92, 255, 0.08)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: '#2C5CFF',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#2C5CFF'
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
                x: { grid: { display: false } },
                y: { 
                    grid: { color: '#F0EFEC' },
                    border: { display: false }
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
                    backgroundColor: '#2C5CFF',
                    borderRadius: 6
                },
                {
                    label: 'Last Week',
                    data: data.last_week,
                    backgroundColor: '#E8E8E4',
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: commonTooltip,
                legend: {
                    labels: { color: '#525252', font: { family: "'Inter', sans-serif" } }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { 
                    grid: { color: '#F0EFEC' },
                    border: { display: false }
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
                <h4 style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">Predicted Spending</h4>
                <div class="val" style="font-size: 1.5rem; font-weight: 700; color: var(--text);">₹${data.predicted_spending.toLocaleString()}</div>
                <p style="font-size: 0.8rem; margin-top:0.5rem; margin-bottom: 0; color: var(--text-muted);">Based on last 3 months average</p>
            </div>
        </div>
        <div class="col-sm-6">
            <div class="forecast-card" style="background: var(--surface); border-radius: var(--radius-md); padding: 24px; border: 1px solid var(--border);">
                <h4 style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">Predicted Savings</h4>
                <div class="val" style="font-size: 1.5rem; font-weight: 700; color: var(--text);">₹${data.predicted_savings.toLocaleString()}</div>
                <p style="font-size: 0.8rem; margin-top:0.5rem; margin-bottom: 0; color: var(--text-muted);">Assuming income of ₹${data.income.toLocaleString()}</p>
            </div>
        </div>
    `;
    container.innerHTML = html;
}

function renderHealthSuggestions(data) {
    const container = document.getElementById('health-suggestions');
    if (!container) return;
    
    if (data.suggestions && data.suggestions.length > 0) {
        let html = '<ul style="margin-left: 1.5rem; margin-bottom: 0; padding-left: 0; list-style-type: disc;">';
        data.suggestions.forEach(s => {
            html += `<li style="margin-bottom: 0.5rem; line-height: 1.4;">${s}</li>`;
        });
        html += '</ul>';
        container.innerHTML = html;
    } else {
        container.innerHTML = '<span style="opacity: 0.7;">No recommendations currently. You are doing great!</span>';
    }
}
