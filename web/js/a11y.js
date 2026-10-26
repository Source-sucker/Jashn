/**
 * Accessibility (a11y) and text formatting utilities for Jashn.
 */

export function announce(message, priority = 'polite') {
  const announcer = document.getElementById('aria-announcer');
  if (announcer) {
    announcer.setAttribute('aria-live', priority);
    announcer.textContent = '';
    // Small timeout ensures screen reader registers text change
    setTimeout(() => {
      announcer.textContent = message;
    }, 50);
  }
}

export function formatINR(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return '₹0';
  const num = Math.round(Number(amount));
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(num);
}

export function formatIndianWords(num) {
  if (!num || isNaN(num) || num <= 0) return '';
  const n = Math.round(num);
  if (n >= 10000000) {
    const cr = (n / 10000000).toFixed(2);
    return `≈ ₹${cr.replace(/\.00$/, '')} Crore`;
  }
  if (n >= 100000) {
    const lk = (n / 100000).toFixed(2);
    return `≈ ₹${lk.replace(/\.00$/, '')} Lakh`;
  }
  if (n >= 1000) {
    const th = (n / 1000).toFixed(1);
    return `≈ ₹${th.replace(/\.0$/, '')} Thousand`;
  }
  return '';
}

export function trapFocus(dialog) {
  const focusable = dialog.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (focusable.length === 0) return () => {};

  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  function handleKeyDown(e) {
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === first) {
          last.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === last) {
          first.focus();
          e.preventDefault();
        }
      }
    } else if (e.key === 'Escape') {
      dialog.close();
    }
  }

  dialog.addEventListener('keydown', handleKeyDown);
  first.focus();

  return () => {
    dialog.removeEventListener('keydown', handleKeyDown);
  };
}
