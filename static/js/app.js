// Arbitrage Advisor Frontend JavaScript

class ArbitrageApp {
    constructor() {
        this.opportunities = [];
        this.scanning = false;
        this.autoRefreshInterval = null;

        this.initializeElements();
        this.attachEventListeners();
        this.loadInitialData();
    }

    initializeElements() {
        // Buttons
        this.discoverBtn = document.getElementById('discoverBtn');
        this.scanBtn = document.getElementById('scanBtn');
        this.refreshBtn = document.getElementById('refreshBtn');

        // Inputs
        this.budgetInput = document.getElementById('budgetInput');
        this.useDiscoveredCheckbox = document.getElementById('useDiscovered');

        // Status elements
        this.scanStatus = document.getElementById('scanStatus');
        this.lastUpdate = document.getElementById('lastUpdate');
        this.totalMarkets = document.getElementById('totalMarkets');
        this.profitableCount = document.getElementById('profitableCount');

        // Table
        this.opportunitiesBody = document.getElementById('opportunitiesBody');

        // Modal
        this.modal = document.getElementById('detailModal');
        this.modalContent = document.getElementById('detailContent');
        this.closeModal = document.querySelector('.close');
    }

    attachEventListeners() {
        this.discoverBtn.addEventListener('click', () => this.discoverMarkets());
        this.scanBtn.addEventListener('click', () => this.startScan());
        this.refreshBtn.addEventListener('click', () => this.refreshOpportunities());

        this.closeModal.addEventListener('click', () => {
            this.modal.style.display = 'none';
        });

        window.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.modal.style.display = 'none';
            }
        });
    }

    async loadInitialData() {
        await this.updateStatus();
        await this.refreshOpportunities();
    }

    async discoverMarkets() {
        this.setButtonLoading(this.discoverBtn, true);
        this.updateStatusText('Discovering markets...');

        try {
            const response = await fetch('/api/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification(`✓ Discovered ${data.pairs_found} market pairs!`, 'success');
                this.updateStatusText('Discovery complete');
                this.renderDiscoveredPairs(data.pairs || []);
            } else {
                this.showNotification(`Error: ${data.error}`, 'error');
                this.updateStatusText('Discovery failed');
            }
        } catch (error) {
            this.showNotification(`Error: ${error.message}`, 'error');
            this.updateStatusText('Discovery failed');
        } finally {
            this.setButtonLoading(this.discoverBtn, false);
        }
    }

    async startScan() {
        this.setButtonLoading(this.scanBtn, true);
        this.scanning = true;
        this.updateStatusText('Scanning...');

        try {
            const response = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    budget: parseFloat(this.budgetInput.value),
                    use_discovered: this.useDiscoveredCheckbox.checked
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showNotification('Scan started! Refreshing results...', 'success');
                // Start polling for results
                this.pollForResults();
            } else {
                this.showNotification(`Error: ${data.error}`, 'error');
                this.scanning = false;
                this.setButtonLoading(this.scanBtn, false);
            }
        } catch (error) {
            this.showNotification(`Error: ${error.message}`, 'error');
            this.scanning = false;
            this.setButtonLoading(this.scanBtn, false);
        }
    }

    async pollForResults() {
        const pollInterval = setInterval(async () => {
            await this.updateStatus();
            await this.refreshOpportunities();

            // Stop polling when scan is complete
            if (!this.scanning) {
                clearInterval(pollInterval);
                this.setButtonLoading(this.scanBtn, false);
            }
        }, 2000);
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();

            this.scanning = status.scanning;
            this.updateStatusText(status.scanning ? 'Scanning...' : 'Ready');

            if (status.last_update) {
                const date = new Date(status.last_update);
                this.lastUpdate.textContent = date.toLocaleTimeString();
            }

            this.totalMarkets.textContent = status.total_markets || 0;
            this.profitableCount.textContent = status.profitable_count || 0;

            if (status.error) {
                this.showNotification(`Error: ${status.error}`, 'error');
            }
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    async refreshOpportunities() {
        try {
            const response = await fetch('/api/opportunities');
            const data = await response.json();

            this.opportunities = data.opportunities || [];
            this.renderOpportunities();
        } catch (error) {
            console.error('Error refreshing opportunities:', error);
        }
    }

    renderOpportunities() {
        if (this.opportunities.length === 0) {
            this.opportunitiesBody.innerHTML = `
                <tr>
                    <td colspan="9" class="empty-state">
                        No opportunities found. Click "Auto-Discover Markets" then "Scan for Arbitrage"
                    </td>
                </tr>
            `;
            return;
        }

        this.opportunitiesBody.innerHTML = this.opportunities.map((opp, index) => {
            const roiClass = opp.roi_percent >= 1 ? 'roi-alert' :
                           opp.roi_percent > 0 ? 'roi-positive' : 'roi-negative';

            const profitBadge = opp.roi_percent > 0 ? 'badge-success' : 'badge-danger';

            return `
                <tr onclick="app.showDetails(${index})">
                    <td>${index + 1}</td>
                    <td>${this.truncate(opp.market_name, 30)}</td>
                    <td><span class="badge badge-warning">${opp.direction}</span></td>
                    <td class="${roiClass}">${opp.roi_percent.toFixed(2)}%</td>
                    <td class="${roiClass}">$${opp.avg_profit.toFixed(2)}</td>
                    <td>$${opp.total_cost.toFixed(2)}</td>
                    <td>
                        <span class="badge ${opp.poly_side === 'YES' ? 'badge-success' : 'badge-danger'}">
                            ${opp.poly_side}
                        </span>
                        ${opp.poly_quantity}
                    </td>
                    <td>
                        <span class="badge ${opp.kalshi_side === 'YES' ? 'badge-success' : 'badge-danger'}">
                            ${opp.kalshi_side}
                        </span>
                        ${opp.kalshi_quantity}
                    </td>
                    <td>
                        <button class="btn btn-primary" style="padding: 0.5rem 1rem; font-size: 0.875rem;">
                            View Details
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderDiscoveredPairs(pairs) {
        const section = document.getElementById('discoveredSection');
        const grid = document.getElementById('discoveredGrid');
        const count = document.getElementById('discoveredCount');

        if (!pairs.length) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';
        count.textContent = `${pairs.length} pair${pairs.length !== 1 ? 's' : ''}`;

        grid.innerHTML = pairs.map(pair => {
            const score = pair.similarity_score || 0;
            const pct = Math.round(score * 100);
            const color = score >= 0.5 ? 'var(--success)' :
                          score >= 0.4 ? 'var(--warning)' : 'var(--text-secondary)';

            return `
                <div class="pair-card">
                    <div class="pair-score">
                        <span class="platform-tag" style="background: rgba(16,185,129,0.15); color: var(--success); font-size: 0.75rem;">Match</span>
                        <div class="score-bar">
                            <div class="score-bar-fill" style="width: ${pct}%; background: ${color};"></div>
                        </div>
                        <span class="score-label" style="color: ${color};">${pct}%</span>
                    </div>
                    <div class="pair-market">
                        <span class="platform-tag poly">POLY</span>
                        <span class="pair-title">${this.truncate(pair.poly_title || '', 80)}</span>
                    </div>
                    <div class="pair-market">
                        <span class="platform-tag kalshi">KALSHI</span>
                        <span class="pair-title">${this.truncate(pair.kalshi_title || '', 80)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    showDetails(index) {
        const opp = this.opportunities[index];

        this.modalContent.innerHTML = `
            <h2>${opp.market_name}</h2>

            <div class="detail-section">
                <h3>📊 Overview</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="label">Strategy</div>
                        <div class="value">${opp.direction}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Net ROI</div>
                        <div class="value" style="color: ${opp.roi_percent >= 1 ? 'var(--warning)' : opp.roi_percent > 0 ? 'var(--success)' : 'var(--text-secondary)'}">
                            ${opp.roi_percent.toFixed(2)}%
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Expected Profit</div>
                        <div class="value" style="color: var(--success)">$${opp.avg_profit.toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Total Capital</div>
                        <div class="value">$${opp.total_cost.toFixed(2)}</div>
                    </div>
                </div>
            </div>

            <div class="detail-section">
                <h3>💰 Polymarket Position</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="label">Side</div>
                        <div class="value">${opp.poly_side}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Quantity</div>
                        <div class="value">${opp.poly_quantity} contracts</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Limit Price</div>
                        <div class="value">$${opp.poly_price.toFixed(4)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Total Cost</div>
                        <div class="value">$${opp.poly_cost.toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Fee</div>
                        <div class="value">$${opp.poly_fee.toFixed(2)}</div>
                    </div>
                </div>
            </div>

            <div class="detail-section">
                <h3>📈 Kalshi Position</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="label">Side</div>
                        <div class="value">${opp.kalshi_side}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Quantity</div>
                        <div class="value">${opp.kalshi_quantity} contracts</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Limit Price</div>
                        <div class="value">${opp.kalshi_price.toFixed(1)}¢</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Total Cost</div>
                        <div class="value">$${opp.kalshi_cost.toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Fee</div>
                        <div class="value">$${opp.kalshi_fee.toFixed(2)}</div>
                    </div>
                </div>
            </div>

            <div class="detail-section">
                <h3>🎯 Expected Outcomes</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="label">Profit if YES</div>
                        <div class="value" style="color: var(--success)">$${opp.outcome_yes_profit.toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Profit if NO</div>
                        <div class="value" style="color: var(--success)">$${opp.outcome_no_profit.toFixed(2)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="label">Total Fees</div>
                        <div class="value">$${opp.total_fees.toFixed(2)}</div>
                    </div>
                </div>
            </div>

            ${opp.roi_percent >= 1 ? `
                <div class="order-instructions">
                    <h4>📋 Manual Execution Instructions</h4>
                    <div class="order-step">
                        <strong>Step 1: Polymarket</strong><br>
                        → Buy ${opp.poly_quantity} ${opp.poly_side} contracts<br>
                        → Use LIMIT order at $${opp.poly_price.toFixed(4)}<br>
                        → Expected cost: $${opp.poly_cost.toFixed(2)} + $${opp.poly_fee.toFixed(2)} fee
                    </div>
                    <div class="order-step">
                        <strong>Step 2: Kalshi</strong><br>
                        → Buy ${opp.kalshi_quantity} ${opp.kalshi_side} contracts<br>
                        → Use LIMIT order at ${opp.kalshi_price.toFixed(1)}¢<br>
                        → Expected cost: $${opp.kalshi_cost.toFixed(2)} + $${opp.kalshi_fee.toFixed(2)} fee
                    </div>
                    <div class="order-step" style="background: rgba(239, 68, 68, 0.1); border-left: 3px solid var(--danger);">
                        <strong>⚠️ Critical Safety Rules:</strong><br>
                        • Use LIMIT orders only (never market orders)<br>
                        • Place both orders as quickly as possible<br>
                        • If only one fills, CANCEL the other immediately<br>
                        • Never leave unhedged positions open
                    </div>
                </div>
            ` : ''}
        `;

        this.modal.style.display = 'block';
    }

    updateStatusText(text) {
        this.scanStatus.textContent = text;
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button._originalHTML = button.innerHTML;
            button.disabled = true;
            button.innerHTML = `<span class="spinner"></span> ${button.textContent}`;
        } else {
            button.disabled = false;
            if (button._originalHTML) {
                button.innerHTML = button._originalHTML;
            }
        }
    }

    showNotification(message, type = 'info') {
        // Simple alert for now - can be replaced with toast notifications
        console.log(`[${type}] ${message}`);

        // Update status bar color briefly
        const statusBar = document.getElementById('statusBar');
        const originalBg = statusBar.style.background;

        if (type === 'success') {
            statusBar.style.background = 'rgba(16, 185, 129, 0.2)';
        } else if (type === 'error') {
            statusBar.style.background = 'rgba(239, 68, 68, 0.2)';
        }

        setTimeout(() => {
            statusBar.style.background = originalBg;
        }, 2000);
    }

    truncate(str, maxLen) {
        return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
    }
}

// Initialize app when DOM is loaded
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ArbitrageApp();

    // Auto-refresh every 30 seconds
    setInterval(() => {
        if (!app.scanning) {
            app.refreshOpportunities();
        }
    }, 30000);
});
