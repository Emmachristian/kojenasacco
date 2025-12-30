/**
 * HTMX Modal Management with SweetAlert2
 * 
 * Handles all modal operations and notifications for HTMX-powered modals
 * 
 * Features:
 * - Automatic modal opening/closing
 * - SweetAlert2 notifications
 * - Custom header handling
 * - Error handling
 * - Loading states
 * 
 * @requires Bootstrap 5
 * @requires HTMX
 * @requires SweetAlert2
 */

(function() {
    'use strict';
    
    // =============================================================================
    // CONFIGURATION
    // =============================================================================
    
    const CONFIG = {
        modalId: 'global-modal',
        modalContentId: 'modal-content',
        modalBackdrop: 'static',
        modalKeyboard: false,
        successAutoClose: 3000, // Auto-close success alerts after 3 seconds
        enableLogging: true // Set to false in production
    };
    
    
    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================
    
    /**
     * Log messages (only if logging is enabled)
     */
    function log(message, data = null) {
        if (CONFIG.enableLogging) {
            if (data) {
                console.log(`[HTMX Modal] ${message}`, data);
            } else {
                console.log(`[HTMX Modal] ${message}`);
            }
        }
    }
    
    /**
     * Log errors (always logged regardless of config)
     */
    function logError(message, error = null) {
        if (error) {
            console.error(`[HTMX Modal] ${message}`, error);
        } else {
            console.error(`[HTMX Modal] ${message}`);
        }
    }
    
    
    // =============================================================================
    // MODAL MANAGEMENT
    // =============================================================================
    
    let modalInstance = null;
    const modalElement = document.getElementById(CONFIG.modalId);
    
    /**
     * Initialize modal instance
     */
    function initModal() {
        if (modalElement && typeof bootstrap !== 'undefined') {
            modalInstance = new bootstrap.Modal(modalElement, {
                backdrop: CONFIG.modalBackdrop,
                keyboard: CONFIG.modalKeyboard
            });
            log('Modal instance initialized');
            return true;
        } else {
            logError('Failed to initialize modal - element or Bootstrap not found');
            return false;
        }
    }
    
    /**
     * Show the modal
     */
    function showModal() {
        if (modalInstance) {
            modalInstance.show();
            log('Modal shown');
        } else {
            logError('Cannot show modal - instance not initialized');
        }
    }
    
    /**
     * Hide the modal
     */
    function hideModal() {
        if (modalInstance) {
            modalInstance.hide();
            log('Modal hidden');
        }
    }
    
    /**
     * Clear modal content
     */
    function clearModalContent() {
        const contentElement = document.getElementById(CONFIG.modalContentId);
        if (contentElement) {
            contentElement.innerHTML = '';
            log('Modal content cleared');
        }
    }
    
    /**
     * Show loading spinner in modal
     */
    function showModalLoading() {
        const contentElement = document.getElementById(CONFIG.modalContentId);
        if (contentElement) {
            contentElement.innerHTML = `
                <div class="modal-body text-center py-5">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-3 text-muted">Loading...</p>
                </div>
            `;
        }
    }
    
    
    // =============================================================================
    // SWEETALERT2 MANAGEMENT
    // =============================================================================
    
    /**
     * Show SweetAlert2 notification
     * 
     * @param {string} message - Alert message
     * @param {string} type - Alert type (success, error, warning, info, question)
     * @param {string|null} title - Optional custom title
     */
    function showSweetAlert(message, type, title) {
        type = type || 'success';
        
        // Validate SweetAlert2 is available
        if (typeof Swal === 'undefined') {
            logError('SweetAlert2 not loaded - falling back to console');
            console.log(`[${type.toUpperCase()}] ${title || ''}: ${message}`);
            return;
        }
        
        // Icon mapping
        const iconMap = {
            'success': 'success',
            'error': 'error',
            'warning': 'warning',
            'info': 'info',
            'question': 'question'
        };
        
        // Default titles
        const defaultTitles = {
            'success': 'Success!',
            'error': 'Error!',
            'warning': 'Warning!',
            'info': 'Information',
            'question': 'Are you sure?'
        };
        
        // Button colors
        const buttonColors = {
            'success': '#28a745',
            'error': '#dc3545',
            'warning': '#ffc107',
            'info': '#17a2b8',
            'question': '#6c757d'
        };
        
        const icon = iconMap[type] || 'info';
        const alertTitle = title || defaultTitles[type] || 'Notification';
        const buttonColor = buttonColors[type] || '#17a2b8';
        
        // Show alert
        Swal.fire({
            icon: icon,
            title: alertTitle,
            text: message,
            confirmButtonText: 'OK',
            confirmButtonColor: buttonColor,
            timer: type === 'success' ? CONFIG.successAutoClose : null,
            timerProgressBar: type === 'success',
            customClass: {
                confirmButton: 'btn btn-primary',
            },
            buttonsStyling: false
        });
        
        log(`SweetAlert shown: ${type} - ${message}`);
    }
    
    /**
     * Show confirmation dialog
     * 
     * @param {string} message - Confirmation message
     * @param {string} title - Dialog title
     * @param {string} confirmText - Confirm button text
     * @param {string} cancelText - Cancel button text
     * @returns {Promise} SweetAlert2 promise
     */
    function showConfirmation(message, title, confirmText, cancelText) {
        if (typeof Swal === 'undefined') {
            logError('SweetAlert2 not loaded');
            return Promise.reject('SweetAlert2 not available');
        }
        
        return Swal.fire({
            icon: 'question',
            title: title || 'Are you sure?',
            text: message,
            showCancelButton: true,
            confirmButtonText: confirmText || 'Yes, proceed',
            cancelButtonText: cancelText || 'Cancel',
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            customClass: {
                confirmButton: 'btn btn-danger me-2',
                cancelButton: 'btn btn-secondary'
            },
            buttonsStyling: false,
            reverseButtons: true
        });
    }
    
    
    // =============================================================================
    // HTMX EVENT HANDLERS
    // =============================================================================
    
    /**
     * Handle HTMX after swap event
     * Shows modal when content is loaded into modal container
     */
    document.addEventListener('htmx:afterSwap', function(event) {
        if (event.detail.target.id === CONFIG.modalContentId) {
            showModal();
        }
    });
    
    /**
     * Handle HTMX before request event
     * Shows loading spinner for modal requests
     */
    document.addEventListener('htmx:beforeRequest', function(event) {
        if (event.detail.target.id === CONFIG.modalContentId) {
            showModalLoading();
        }
    });
    
    /**
     * Handle HTMX before swap event
     * Process custom headers and show alerts
     */
    document.addEventListener('htmx:beforeSwap', function(event) {
        const xhr = event.detail.xhr;
        
        // Check for alert message in headers
        const message = xhr.getResponseHeader('HX-Alert-Message');
        const type = xhr.getResponseHeader('HX-Alert-Type');
        const title = xhr.getResponseHeader('HX-Alert-Title');
        
        if (message) {
            // Delay alert slightly to ensure modal closes first
            setTimeout(function() {
                showSweetAlert(message, type || 'success', title);
            }, 200);
        }
        
        // Check for modal close instruction
        const closeModal = xhr.getResponseHeader('HX-Close-Modal');
        if (closeModal === 'true') {
            setTimeout(hideModal, 100);
        }
    });
    
    /**
     * Handle HTMX response errors
     * Show error alert and close modal
     */
    document.addEventListener('htmx:responseError', function(event) {
        logError('HTMX response error', event.detail);
        
        showSweetAlert(
            'An error occurred while processing your request. Please try again.',
            'error',
            'Request Failed'
        );
        
        hideModal();
    });
    
    /**
     * Handle HTMX network errors
     * Show connection error alert
     */
    document.addEventListener('htmx:sendError', function(event) {
        logError('HTMX network error', event.detail);
        
        showSweetAlert(
            'Unable to connect to the server. Please check your internet connection and try again.',
            'error',
            'Connection Error'
        );
    });
    
    /**
     * Handle HTMX timeout
     */
    document.addEventListener('htmx:timeout', function(event) {
        logError('HTMX timeout', event.detail);
        
        showSweetAlert(
            'The request took too long to complete. Please try again.',
            'warning',
            'Request Timeout'
        );
        
        hideModal();
    });
    
    
    // =============================================================================
    // CUSTOM EVENT HANDLERS
    // =============================================================================
    
    /**
     * Handle custom showAlert event
     */
    document.body.addEventListener('showAlert', function(event) {
        const message = event.detail.message || 'Action completed';
        const type = event.detail.type || 'success';
        const title = event.detail.title || null;
        showSweetAlert(message, type, title);
    });
    
    /**
     * Handle custom closeModal event
     */
    document.body.addEventListener('closeModal', function() {
        hideModal();
    });
    
    
    // =============================================================================
    // BOOTSTRAP MODAL EVENT HANDLERS
    // =============================================================================
    
    /**
     * Clear modal content when fully hidden
     */
    if (modalElement) {
        modalElement.addEventListener('hidden.bs.modal', function() {
            clearModalContent();
        });
    }
    
    
    // =============================================================================
    // GLOBAL API
    // =============================================================================
    
    /**
     * Expose functions globally for use in templates
     */
    window.HTMXModal = {
        // Modal functions
        show: showModal,
        hide: hideModal,
        clear: clearModalContent,
        
        // Alert functions
        showAlert: showSweetAlert,
        showSuccess: function(message, title) {
            showSweetAlert(message, 'success', title);
        },
        showError: function(message, title) {
            showSweetAlert(message, 'error', title);
        },
        showWarning: function(message, title) {
            showSweetAlert(message, 'warning', title);
        },
        showInfo: function(message, title) {
            showSweetAlert(message, 'info', title);
        },
        
        // Confirmation function
        confirm: showConfirmation,
        
        // Configuration
        config: CONFIG
    };
    
    // Also expose shorthand functions
    window.showAlert = showSweetAlert;
    window.showSuccess = window.HTMXModal.showSuccess;
    window.showError = window.HTMXModal.showError;
    window.showWarning = window.HTMXModal.showWarning;
    window.showInfo = window.HTMXModal.showInfo;
    window.confirmAction = showConfirmation;
    
    
    // =============================================================================
    // INITIALIZATION
    // =============================================================================
    
    /**
     * Initialize on DOM ready
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initModal();
            log('HTMX Modal Management initialized on DOMContentLoaded');
        });
    } else {
        initModal();
        log('HTMX Modal Management initialized immediately');
    }
    
})();