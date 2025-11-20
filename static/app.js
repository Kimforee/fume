// API Base URL
const API_BASE = '';

// Global state
let currentPage = 1;
let pageSize = 20;
let totalPages = 1;
let currentProductId = null;
let currentWebhookId = null;
let uploadTaskId = null;
let progressInterval = null;

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const section = e.target.getAttribute('data-section');
        showSection(section);
    });
});

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    // Show selected section
    document.getElementById(`${sectionName}-section`).classList.add('active');
    document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');
    
    // Load data for section
    if (sectionName === 'products') {
        loadProducts();
    } else if (sectionName === 'webhooks') {
        loadWebhooks();
    }
}

// File Upload
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');

// Drag and drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

async function handleFileUpload(file) {
    if (!file.name.endsWith('.csv')) {
        showToast('Please upload a CSV file', 'error');
        return;
    }
    
    // Show loading state immediately
    const uploadArea = document.getElementById('upload-area');
    const uploadContent = uploadArea.querySelector('.upload-content');
    const originalContent = uploadContent.innerHTML;
    uploadContent.innerHTML = '<div class="loading-spinner"></div><p>Uploading file...</p>';
    uploadArea.style.pointerEvents = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }
        
        const data = await response.json();
        uploadTaskId = data.task_id;
        
        // Show progress container
        document.getElementById('upload-progress').style.display = 'block';
        uploadArea.style.display = 'none';
        
        // Start polling progress
        startProgressPolling(uploadTaskId);
        
        showToast('File uploaded successfully. Processing...', 'success');
    } catch (error) {
        // Restore original content on error
        uploadContent.innerHTML = originalContent;
        uploadArea.style.pointerEvents = 'auto';
        showToast(error.message, 'error');
    }
}

function startProgressPolling(taskId) {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    // Show cancel button
    document.getElementById('cancel-btn').style.display = 'inline-block';
    
    progressInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/tasks/${taskId}/progress`);
            const progress = await response.json();
            
            updateProgressUI(progress);
            
            if (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'cancelled') {
                clearInterval(progressInterval);
                progressInterval = null;
                document.getElementById('cancel-btn').style.display = 'none';
                
                if (progress.status === 'completed') {
                    showToast('Import completed successfully!', 'success');
                    // Reload products if on products section
                    if (document.getElementById('products-section').classList.contains('active')) {
                        loadProducts();
                    }
                } else if (progress.status === 'cancelled') {
                    showToast('Import cancelled', 'error');
                } else {
                    showToast('Import failed. Check errors below.', 'error');
                }
            }
        } catch (error) {
            console.error('Error fetching progress:', error);
        }
    }, 1000);
}

async function cancelUpload() {
    if (!uploadTaskId) return;
    
    if (!confirm('Are you sure you want to cancel this import?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/tasks/${uploadTaskId}/cancel`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to cancel task');
        }
        
        showToast('Import cancelled', 'success');
        document.getElementById('cancel-btn').style.display = 'none';
        
        // Stop polling
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
    } catch (error) {
        showToast('Error cancelling import', 'error');
    }
}

function updateProgressUI(progress) {
    const statusEl = document.getElementById('progress-status');
    const percentageEl = document.getElementById('progress-percentage');
    const fillEl = document.getElementById('progress-fill');
    const detailsEl = document.getElementById('progress-details');
    const errorsEl = document.getElementById('upload-errors');
    
    statusEl.textContent = progress.message || progress.status;
    percentageEl.textContent = `${Math.round(progress.progress)}%`;
    fillEl.style.width = `${progress.progress}%`;
    
    let details = [];
    if (progress.total_rows) details.push(`Total: ${progress.total_rows}`);
    if (progress.processed_rows !== undefined) details.push(`Processed: ${progress.processed_rows}`);
    if (progress.successful_rows !== undefined) details.push(`Successful: ${progress.successful_rows}`);
    if (progress.failed_rows !== undefined) details.push(`Failed: ${progress.failed_rows}`);
    
    detailsEl.textContent = details.join(' | ');
    
    // Show errors if any
    if (progress.errors && progress.errors.length > 0) {
        errorsEl.style.display = 'block';
        errorsEl.innerHTML = '<strong>Errors:</strong><ul>' + 
            progress.errors.map(e => `<li>${e}</li>`).join('') + 
            '</ul>';
    } else {
        errorsEl.style.display = 'none';
    }
}

// Products
async function loadProducts(page = 1) {
    const sku = document.getElementById('filter-sku').value;
    const name = document.getElementById('filter-name').value;
    const description = document.getElementById('filter-description').value;
    const active = document.getElementById('filter-active').value;
    
    const params = new URLSearchParams({
        page: page,
        page_size: pageSize
    });
    
    if (sku) params.append('sku', sku);
    if (name) params.append('name', name);
    if (description) params.append('description', description);
    if (active) params.append('active', active);
    
    try {
        const response = await fetch(`${API_BASE}/api/products?${params}`);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const data = await response.json();
        
        currentPage = data.page;
        totalPages = data.total_pages;
        
        renderProducts(data.items);
        updatePagination();
    } catch (error) {
        console.error('Error loading products:', error);
        showToast('Error loading products: ' + error.message, 'error');
        document.getElementById('products-table-body').innerHTML = 
            '<tr><td colspan="6" class="loading">Error loading products</td></tr>';
    }
}

function renderProducts(products) {
    const tbody = document.getElementById('products-table-body');
    
    if (products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">No products found</td></tr>';
        return;
    }
    
    tbody.innerHTML = products.map(product => `
        <tr>
            <td>${product.id}</td>
            <td>${escapeHtml(product.name)}</td>
            <td>${escapeHtml(product.sku)}</td>
            <td>${escapeHtml(product.description || '')}</td>
            <td><span class="status-badge ${product.active ? 'status-active' : 'status-inactive'}">
                ${product.active ? 'Active' : 'Inactive'}
            </span></td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-primary btn-sm" onclick="editProduct(${product.id})">Edit</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteProduct(${product.id})">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function updatePagination() {
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages || 1}`;
    document.getElementById('prev-page').disabled = currentPage <= 1;
    document.getElementById('next-page').disabled = currentPage >= totalPages;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {
        loadProducts(newPage);
    }
}

// Product Modal
function showProductModal(productId = null) {
    currentProductId = productId;
    const modal = document.getElementById('product-modal');
    const form = document.getElementById('product-form');
    const title = document.getElementById('product-modal-title');
    
    if (productId) {
        title.textContent = 'Edit Product';
        // Load product data
        fetch(`${API_BASE}/api/products/${productId}`)
            .then(r => r.json())
            .then(product => {
                document.getElementById('product-id').value = product.id;
                document.getElementById('product-name').value = product.name;
                document.getElementById('product-sku').value = product.sku;
                document.getElementById('product-description').value = product.description || '';
                document.getElementById('product-active').checked = product.active;
            });
    } else {
        title.textContent = 'Add Product';
        form.reset();
        document.getElementById('product-id').value = '';
    }
    
    modal.classList.add('active');
}

function closeProductModal() {
    document.getElementById('product-modal').classList.remove('active');
    currentProductId = null;
}

document.getElementById('product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const productData = {
        name: document.getElementById('product-name').value,
        sku: document.getElementById('product-sku').value,
        description: document.getElementById('product-description').value,
        active: document.getElementById('product-active').checked
    };
    
    const productId = document.getElementById('product-id').value;
    const url = productId ? `${API_BASE}/api/products/${productId}` : `${API_BASE}/api/products`;
    const method = productId ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Operation failed');
        }
        
        showToast(`Product ${productId ? 'updated' : 'created'} successfully`, 'success');
        closeProductModal();
        loadProducts(currentPage);
    } catch (error) {
        showToast(error.message, 'error');
    }
});

async function editProduct(id) {
    showProductModal(id);
}

async function deleteProduct(id) {
    if (!confirm('Are you sure you want to delete this product?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/products/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Delete failed');
        
        showToast('Product deleted successfully', 'success');
        loadProducts(currentPage);
    } catch (error) {
        showToast('Error deleting product', 'error');
    }
}

function confirmBulkDelete() {
    if (!confirm('Are you sure you want to delete ALL products? This cannot be undone.')) return;
    
    fetch(`${API_BASE}/api/products/bulk`, {
        method: 'DELETE'
    })
    .then(r => r.json())
    .then(data => {
        showToast(`Deleted ${data.deleted_count} products`, 'success');
        loadProducts(1);
    })
    .catch(error => {
        showToast('Error deleting products', 'error');
    });
}

// Webhooks
async function loadWebhooks() {
    try {
        const response = await fetch(`${API_BASE}/api/webhooks`);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const webhooks = await response.json();
        renderWebhooks(webhooks);
    } catch (error) {
        console.error('Error loading webhooks:', error);
        showToast('Error loading webhooks: ' + error.message, 'error');
        document.getElementById('webhooks-table-body').innerHTML = 
            '<tr><td colspan="5" class="loading">Error loading webhooks</td></tr>';
    }
}

function renderWebhooks(webhooks) {
    const tbody = document.getElementById('webhooks-table-body');
    
    if (webhooks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading">No webhooks found</td></tr>';
        return;
    }
    
    tbody.innerHTML = webhooks.map(webhook => `
        <tr>
            <td>${webhook.id}</td>
            <td>${escapeHtml(webhook.url)}</td>
            <td>${webhook.event_types.join(', ')}</td>
            <td><span class="status-badge ${webhook.enabled ? 'status-active' : 'status-inactive'}">
                ${webhook.enabled ? 'Enabled' : 'Disabled'}
            </span></td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-primary btn-sm" onclick="editWebhook(${webhook.id})">Edit</button>
                    <button class="btn btn-primary btn-sm" onclick="testWebhook(${webhook.id})">Test</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteWebhook(${webhook.id})">Delete</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function showWebhookModal(webhookId = null) {
    currentWebhookId = webhookId;
    const modal = document.getElementById('webhook-modal');
    const form = document.getElementById('webhook-form');
    const title = document.getElementById('webhook-modal-title');
    
    if (webhookId) {
        title.textContent = 'Edit Webhook';
        fetch(`${API_BASE}/api/webhooks/${webhookId}`)
            .then(r => r.json())
            .then(webhook => {
                document.getElementById('webhook-id').value = webhook.id;
                document.getElementById('webhook-url').value = webhook.url;
                document.getElementById('webhook-enabled').checked = webhook.enabled;
                // Set event types
                document.querySelectorAll('input[name="event-types"]').forEach(cb => {
                    cb.checked = webhook.event_types.includes(cb.value);
                });
            });
    } else {
        title.textContent = 'Add Webhook';
        form.reset();
        document.getElementById('webhook-id').value = '';
    }
    
    modal.classList.add('active');
}

function closeWebhookModal() {
    document.getElementById('webhook-modal').classList.remove('active');
    currentWebhookId = null;
}

document.getElementById('webhook-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const eventTypes = Array.from(document.querySelectorAll('input[name="event-types"]:checked'))
        .map(cb => cb.value);
    
    if (eventTypes.length === 0) {
        showToast('Please select at least one event type', 'error');
        return;
    }
    
    const webhookData = {
        url: document.getElementById('webhook-url').value,
        event_types: eventTypes,
        enabled: document.getElementById('webhook-enabled').checked
    };
    
    const webhookId = document.getElementById('webhook-id').value;
    const url = webhookId ? `${API_BASE}/api/webhooks/${webhookId}` : `${API_BASE}/api/webhooks`;
    const method = webhookId ? 'PUT' : 'POST';
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(webhookData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Operation failed');
        }
        
        showToast(`Webhook ${webhookId ? 'updated' : 'created'} successfully`, 'success');
        closeWebhookModal();
        loadWebhooks();
    } catch (error) {
        showToast(error.message, 'error');
    }
});

async function editWebhook(id) {
    showWebhookModal(id);
}

async function deleteWebhook(id) {
    if (!confirm('Are you sure you want to delete this webhook?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/webhooks/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Delete failed');
        
        showToast('Webhook deleted successfully', 'success');
        loadWebhooks();
    } catch (error) {
        showToast('Error deleting webhook', 'error');
    }
}

async function testWebhook(id) {
    try {
        const response = await fetch(`${API_BASE}/api/webhooks/${id}/test`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.success) {
            showToast(`Webhook test successful (${result.status_code}) - ${result.response_time_ms}ms`, 'success');
        } else {
            showToast('Webhook test failed', 'error');
        }
    } catch (error) {
        showToast('Error testing webhook', 'error');
    }
}

// Utility functions
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Show upload section by default
    showSection('upload');
});

