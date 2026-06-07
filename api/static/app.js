document.addEventListener('DOMContentLoaded', () => {
    // Determine WS URL based on current host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost:8000';
    const wsUrl = `${protocol}//${host}/ws`;
    
    let ws;
    
    // Make closure function globally accessible for inline onclick
    window.approveClosure = function(nodeId, event) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: 'close_gate',
                node_id: nodeId
            }));
            if (event && event.target) {
                event.target.innerHTML = 'CLOSING...';
                event.target.style.opacity = '0.7';
                event.target.disabled = true;
            }
        }
    };
    
    window.openGate = function(nodeId, event) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: 'open_gate',
                node_id: nodeId
            }));
            if (event && event.target) {
                event.target.innerHTML = 'OPENING...';
                event.target.style.opacity = '0.7';
                event.target.disabled = true;
            }
        }
    };
    
    // Control Panel logic
    document.getElementById('control-scenario').addEventListener('change', (e) => {
        fetch(`/api/scenario?scenario=${e.target.value}&weather=${document.getElementById('control-weather').value}`, {method: 'POST'});
    });
    document.getElementById('control-weather').addEventListener('change', (e) => {
        fetch(`/api/scenario?scenario=${document.getElementById('control-scenario').value}&weather=${e.target.value}`, {method: 'POST'});
    });
    
    const tickSlider = document.getElementById('control-tick');
    tickSlider.addEventListener('input', (e) => {
        document.getElementById('tick-val-display').textContent = e.target.value + 's';
    });
    tickSlider.addEventListener('change', (e) => {
        fetch(`/api/settings/tick?interval=${e.target.value}`, {method: 'POST'});
    });
    
    // Control Panel Toggle Logic
    const controlsHeader = document.getElementById('controls-header');
    const controlsBody = document.getElementById('controls-body');
    const controlsToggleIcon = document.getElementById('controls-toggle-icon');
    
    if (controlsHeader) {
        controlsHeader.addEventListener('click', () => {
            if (controlsBody.style.maxHeight === '0px') {
                controlsBody.style.maxHeight = '500px';
                controlsBody.style.opacity = '1';
                controlsBody.style.marginTop = '16px';
                controlsToggleIcon.style.transform = 'rotate(0deg)';
            } else {
                controlsBody.style.maxHeight = '0px';
                controlsBody.style.opacity = '0';
                controlsBody.style.marginTop = '0px';
                controlsToggleIcon.style.transform = 'rotate(-90deg)';
            }
        });
    }

    // Vis.js Network Setup
    const container = document.getElementById('network-graph');
    const visNodes = new vis.DataSet();
    const visEdges = new vis.DataSet();
    const data = {
        nodes: visNodes,
        edges: visEdges
    };
    const options = {
        nodes: {
            shape: 'dot',
            font: {
                color: '#e2e8f0',
                size: 14,
                face: 'Outfit'
            },
            borderWidth: 2,
            shadow: true
        },
        edges: {
            smooth: {
                type: 'continuous'
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.5 }
            }
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -120,
                centralGravity: 0.005,
                springLength: 160,
                springConstant: 0.06,
                damping: 0.45,
                avoidOverlap: 1.0
            },
            stabilization: {
                iterations: 300
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 80,
            navigationButtons: true,
            keyboard: true,
            dragNodes: false
        }
    };
    
    const network = new vis.Network(container, data, options);
    
    // Freeze the graph layout permanently once the initial physics settle
    network.once("stabilizationIterationsDone", function() {
        network.setOptions({ physics: false });
    });
    
    
    // Fullscreen Logic
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    const graphPanel = document.getElementById('graph-panel');
    
    fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            graphPanel.requestFullscreen().catch(err => {
                console.log(`Error attempting to enable fullscreen: ${err.message}`);
            });
        } else {
            document.exitFullscreen();
        }
    });
    
    document.addEventListener('fullscreenchange', () => {
        if (document.fullscreenElement) {
            fullscreenBtn.textContent = '✖ Close';
            graphPanel.style.background = 'var(--bg-color)';
        } else {
            fullscreenBtn.textContent = '⛶ Expand';
            graphPanel.style.background = 'var(--panel-bg)';
        }
    });
    
    function connect() {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            document.getElementById('val-connection').textContent = 'Connected';
            document.getElementById('val-connection').style.color = 'var(--low-color)';
            document.getElementById('val-connection').style.textShadow = '0 0 8px rgba(0,230,168,0.4)';
        };
        
        ws.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            if (payload.type === 'state_update') {
                updateDashboard(payload);
            }
        };
        
        ws.onclose = () => {
            document.getElementById('val-connection').textContent = 'Disconnected';
            document.getElementById('val-connection').style.color = 'var(--critical-color)';
            document.getElementById('val-connection').style.textShadow = '0 0 8px rgba(255,51,102,0.4)';
            // Reconnect after 3 seconds
            setTimeout(connect, 3000);
        };
        
        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            ws.close();
        };
    }
    
    function updateDashboard(data) {
        // Update header info
        document.getElementById('val-scenario').textContent = data.scenario.toUpperCase();
        document.getElementById('val-weather').textContent = data.weather.toUpperCase();
        document.getElementById('val-tick').textContent = data.tick;
        
        // Sync control panel with active backend state
        if (document.activeElement.id !== 'control-scenario') {
            document.getElementById('control-scenario').value = data.scenario;
        }
        if (document.activeElement.id !== 'control-weather') {
            document.getElementById('control-weather').value = data.weather;
        }
        if (document.activeElement.id !== 'control-tick') {
            const ti = data.tick_interval || 30;
            document.getElementById('control-tick').value = ti;
            document.getElementById('tick-val-display').textContent = ti + 's';
        }
        
        // --- 1. Update Nodes Table ---
        const tbody = document.getElementById('nodes-tbody');
        
        // Sort nodes by load_pct descending
        const nodeList = Object.values(data.nodes);
        nodeList.sort((a, b) => b.load_pct - a.load_pct);
        
        const currentNodeIds = new Set(nodeList.map(n => 'node-row-' + n.node_id));
        
        // Remove stale rows
        Array.from(tbody.children).forEach(row => {
            if (row.id && row.id.startsWith('node-row-') && !currentNodeIds.has(row.id)) {
                row.remove();
            }
            if (!row.id && nodeList.length > 0) {
                row.remove();
            }
        });
        
        nodeList.forEach((node, index) => {
            let tr = document.getElementById('node-row-' + node.node_id);
            if (!tr) {
                tr = document.createElement('tr');
                tr.id = 'node-row-' + node.node_id;
                tr.innerHTML = `
                    <td class="col-node"></td>
                    <td class="col-load">
                        <div class="load-text" style="font-size:12px; margin-bottom: 2px;"></div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill"></div>
                        </div>
                    </td>
                    <td class="col-risk"><span class="risk-badge"></span></td>
                `;
                tbody.appendChild(tr);
            }
            
            if (tbody.children[index] !== tr) {
                tbody.insertBefore(tr, tbody.children[index]);
            }
            
            const colNode = tr.querySelector('.col-node');
            colNode.innerHTML = `<strong>${node.name}</strong><br><span style="font-size:10px; color:#64748b;">${node.priority}</span>`;
            
            tr.querySelector('.load-text').textContent = `${node.fused_occupancy.toLocaleString()} / ${node.safe_threshold.toLocaleString()}`;
            
            const fill = tr.querySelector('.progress-bar-fill');
            fill.style.width = Math.min(node.load_pct, 100) + '%';
            fill.style.background = node.risk_color;
            
            const badge = tr.querySelector('.risk-badge');
            badge.textContent = node.risk_level;
            badge.style.backgroundColor = node.risk_color;
            badge.style.color = (node.risk_level === 'CRITICAL' || node.risk_level === 'HIGH') ? '#fff' : '#000';
        });
        
        // --- 3. Render Alerts ---
        const alertsContainer = document.getElementById('alerts-container');
        let hasAlerts = false;
        const activeAlertIds = new Set();

        if (data.alerts && data.alerts.length > 0) {
            hasAlerts = true;
            data.alerts.forEach(alert => {
                const isClosed = data.approved_closures && data.approved_closures.includes(alert.node_id);
                const alertId = 'alert-card-' + alert.node_id;
                activeAlertIds.add(alertId);
                
                let div = document.getElementById(alertId);
                if (!div) {
                    div = document.createElement('div');
                    div.id = alertId;
                    div.className = 'alert-card';
                    alertsContainer.appendChild(div);
                }
                
                if (alert.risk_level === 'HIGH') {
                    div.style.background = 'linear-gradient(135deg, rgba(255, 153, 51, 0.15) 0%, rgba(255, 153, 51, 0.05) 100%)';
                    div.style.borderColor = 'rgba(255, 153, 51, 0.3)';
                    div.style.borderLeftColor = 'var(--high-color)';
                } else if (alert.risk_level === 'CRITICAL') {
                    div.style.background = 'linear-gradient(135deg, rgba(255, 51, 102, 0.15) 0%, rgba(255, 51, 102, 0.05) 100%)';
                    div.style.borderColor = 'rgba(255, 51, 102, 0.3)';
                    div.style.borderLeftColor = 'var(--critical-color)';
                }
                
                let actionHtml = '';
                if (alert.risk_level === 'CRITICAL') {
                    if (isClosed) {
                        actionHtml = `
                            <div style="margin-top: 10px; padding: 8px; background: rgba(0, 230, 168, 0.1); border-radius: 4px; border: 1px solid rgba(0, 230, 168, 0.3); color: var(--low-color); font-size: 11px; font-weight: 600;">
                                ✅ ACTION TAKEN: Gates Closed. Decongesting area.
                            </div>
                        `;
                    } else {
                        actionHtml = `
                            <div style="margin-top: 10px;">
                                <p style="font-size: 11px; color: #ff3366; margin-bottom: 6px; font-weight: 600;">⚠️ ACTION REQUIRED: Close Gates & Evacuate?</p>
                                <button onclick="window.approveClosure(${alert.node_id}, event)" style="background: var(--critical-color); color: white; border: none; padding: 6px 12px; border-radius: 4px; font-family: 'Outfit'; font-size: 11px; font-weight: 600; cursor: pointer; box-shadow: 0 0 10px rgba(255,51,102,0.4); width: 100%;">APPROVE CLOSURE</button>
                            </div>
                        `;
                    }
                }
                
                div.innerHTML = `
                    <div class="alert-title" style="color: ${alert.risk_level === 'HIGH' ? 'var(--high-color)' : 'var(--critical-color)'}">${alert.risk_level}: ${alert.name}</div>
                    <div class="alert-detail">
                        Load: <strong>${alert.load_pct.toFixed(1)}%</strong><br>
                        Occ: ${alert.fused_occupancy.toLocaleString()} / Cap: ${alert.effective_capacity.toLocaleString()}
                    </div>
                    ${actionHtml}
                `;
            });
        }
        
        // Check for Safe To Reopen alerts
        if (data.approved_closures && data.approved_closures.length > 0) {
            data.approved_closures.forEach(nodeId => {
                const node = Object.values(data.nodes).find(n => n.node_id === nodeId);
                if (node && (node.risk_level === 'LOW' || node.risk_level === 'MEDIUM')) {
                    hasAlerts = true;
                    const alertId = 'alert-reopen-' + nodeId;
                    activeAlertIds.add(alertId);
                    
                    let div = document.getElementById(alertId);
                    if (!div) {
                        div = document.createElement('div');
                        div.id = alertId;
                        div.className = 'alert-card';
                        alertsContainer.appendChild(div);
                    }
                    
                    div.style.background = 'linear-gradient(135deg, rgba(0, 230, 168, 0.15) 0%, rgba(0, 230, 168, 0.05) 100%)';
                    div.style.borderColor = 'rgba(0, 230, 168, 0.3)';
                    div.style.borderLeftColor = '#00e6a8';
                    
                    div.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <div class="alert-title" style="color: #00e6a8;">✅ SAFE TO REOPEN</div>
                                <div class="alert-detail">
                                    <strong>${node.name}</strong> evacuated. Load: ${node.load_pct.toFixed(1)}%.
                                </div>
                            </div>
                            <button onclick="window.openGate(${nodeId}, event)" style="background: rgba(0, 230, 168, 0.2); border: 1px solid rgba(0, 230, 168, 0.4); color: #00e6a8; padding: 6px 12px; border-radius: 4px; font-weight: 600; font-size: 11px; cursor: pointer;">
                                OPEN GATES
                            </button>
                        </div>
                    `;
                }
            });
        }
        
        // Remove stale alerts
        Array.from(alertsContainer.children).forEach(child => {
            if (child.id && child.id.startsWith('alert-') && !activeAlertIds.has(child.id)) {
                child.remove();
            }
        });

        // Handle empty state
        const emptyStateEl = document.getElementById('empty-state-alert');
        if (!hasAlerts) {
            if (!emptyStateEl) {
                alertsContainer.innerHTML = '<p id="empty-state-alert" style="font-size: 13px; color: #64748b; padding: 20px 0; text-align: center;">No active alerts.<br>All nodes operating safely.</p>';
            }
        } else if (emptyStateEl) {
            emptyStateEl.remove();
        }
        
        // --- 3. Update Vis.js Network Graph ---
        if (data.graph && data.graph.nodes && data.graph.edges) {
            // Update Nodes
            const updatedNodes = data.graph.nodes.map(n => {
                // Size mapping: base size 15 + load factor
                const nodeSize = 15 + (n.load_pct / 100) * 15;
                return {
                    id: n.id,
                    label: n.label,
                    shape: n.shape || 'dot',
                    size: nodeSize,
                    color: {
                        background: n.risk_color,
                        border: '#ffffff',
                        highlight: {
                            background: n.risk_color,
                            border: '#ffffff'
                        }
                    },
                    title: `<b>${n.label}</b><br>Load: ${n.load_pct}%<br>Occ: ${n.fused_occupancy}`
                };
            });
            visNodes.update(updatedNodes);
            
            // Update Edges
            const updatedEdges = data.graph.edges.map(e => {
                const edgeId = `${e.from}-${e.to}`;
                return {
                    id: edgeId,
                    from: e.from,
                    to: e.to,
                    width: Math.max(1, Math.min(e.weight / 2, 8)), // Clamp width between 1 and 8
                    color: {
                        color: e.color,
                        highlight: e.color
                    },
                    dashes: e.dashes || false,
                    label: `${e.dist_km}km | ${e.gate_status}`,
                    font: { size: 10, color: '#94a3b8', align: 'middle', background: 'rgba(10,10,24,0.7)' },
                    title: `Weight: ${e.weight}<br>Dist: ${e.dist_km} km<br>Gate: ${e.gate_status}`
                };
            });
            visEdges.update(updatedEdges);
        }
    }
    
    // Initial connection
    connect();
});
