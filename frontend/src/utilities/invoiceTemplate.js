/**
 * MediShop Printable Invoice HTML Generator & Utility
 * ====================================================
 * Generates professionally formatted, print-ready invoices for counter sales.
 * Uses exact values from the backend database as the authoritative source of truth.
 */

export function generateInvoiceHtml(invoice) {
  if (!invoice) return '';

  const pharmacy = {
    name: 'MediShop Healthcare & Retail Pharmacy',
    tagline: 'Licensed Retail Chemist & Druggist',
    address: 'Shop No. 4 & 5, City Medical Plaza, Main Market Road',
    city: 'Mumbai, Maharashtra - 400001',
    phone: '+91 98765 43210',
    email: 'billing@medishop.local',
    gstin: '27AABCU9603R1ZM',
    dlNo: 'MH-MZ2-48192 / MH-MZ2-48193',
  };

  const invoiceDate = invoice.created_at
    ? new Date(invoice.created_at).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    : new Date().toLocaleDateString();

  const customerName = invoice.customer_name || 'Walk-in Customer';
  const customerPhone = invoice.customer_phone || 'N/A';
  const customerAddress = invoice.customer_address || 'Counter Client';
  const doctorRef = invoice.doctor_prescription_ref || 'Self / Over-the-counter';
  const cashierName = invoice.cashier_name || 'Registered Pharmacist';

  const items = invoice.items || [];
  const subtotal = Number(invoice.total_amount ?? invoice.net_amount ?? 0);
  const discount = Number(invoice.discount_amount ?? 0);
  const netAmount = Number(invoice.net_amount ?? 0);

  const itemsRows = items
    .map(
      (it, idx) => `
      <tr>
        <td style="text-align: center; padding: 8px 6px; border-bottom: 1px solid #e2e8f0;">${idx + 1}</td>
        <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">
          <strong>${it.medicine_name || 'Medicine'}</strong>
          ${it.dosage_form ? `<span style="font-size: 11px; color: #64748b; margin-left: 4px;">(${it.dosage_form})</span>` : ''}
        </td>
        <td style="padding: 8px; font-family: monospace; font-size: 11px; border-bottom: 1px solid #e2e8f0;">${it.batch_no || '—'}</td>
        <td style="padding: 8px; font-size: 11px; color: #475569; border-bottom: 1px solid #e2e8f0;">${it.expiry_date || '—'}</td>
        <td style="text-align: center; padding: 8px; font-weight: 600; border-bottom: 1px solid #e2e8f0;">${it.quantity ?? 1}</td>
        <td style="text-align: right; padding: 8px; border-bottom: 1px solid #e2e8f0;">$${Number(it.unit_price ?? 0).toFixed(2)}</td>
        <td style="text-align: right; padding: 8px; font-weight: 600; border-bottom: 1px solid #e2e8f0;">$${Number(it.subtotal ?? 0).toFixed(2)}</td>
      </tr>
    `
    )
    .join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Invoice - ${invoice.invoice_no}</title>
  <style>
    @page { size: A4; margin: 15mm; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      margin: 0;
      padding: 24px;
      line-height: 1.4;
      font-size: 12px;
    }
    .invoice-card {
      max-width: 800px;
      margin: 0 auto;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 28px;
      background: #ffffff;
    }
    .header-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    .pharmacy-title { font-size: 20px; font-weight: 800; color: #0284c7; margin: 0 0 4px 0; }
    .badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      background: #ecfdf5;
      color: #047857;
      border: 1px solid #a7f3d0;
    }
    .details-box {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 20px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
    }
    .details-box td { padding: 10px 14px; vertical-align: top; }
    .items-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    .items-table th {
      background: #f1f5f9;
      color: #334155;
      padding: 9px 8px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 2px solid #cbd5e1;
    }
    .totals-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .totals-table td { padding: 5px 8px; text-align: right; }
    .grand-total {
      font-size: 16px;
      font-weight: 800;
      color: #0284c7;
      border-top: 2px solid #0284c7;
      border-bottom: 2px solid #0284c7;
      padding: 8px !important;
    }
    .footer {
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px dashed #cbd5e1;
      font-size: 11px;
      color: #64748b;
      text-align: center;
    }
    .sign-box {
      margin-top: 40px;
      display: flex;
      justify-content: space-between;
      text-align: center;
      font-size: 11px;
    }
    .sign-line {
      display: inline-block;
      width: 180px;
      border-top: 1px solid #94a3b8;
      padding-top: 4px;
      color: #475569;
    }
    @media print {
      body { padding: 0; }
      .invoice-card { border: none; padding: 0; }
      .no-print { display: none !important; }
    }
  </style>
</head>
<body>
  <div class="invoice-card">
    <!-- Header -->
    <table class="header-table">
      <tr>
        <td style="vertical-align: top; width: 60%;">
          <div class="pharmacy-title">${pharmacy.name}</div>
          <div style="color: #475569; font-size: 12px; font-weight: 500;">${pharmacy.tagline}</div>
          <div style="color: #64748b; font-size: 11px; margin-top: 4px;">
            ${pharmacy.address}<br>
            ${pharmacy.city}<br>
            Phone: ${pharmacy.phone} | Email: ${pharmacy.email}
          </div>
          <div style="font-size: 11px; color: #334155; margin-top: 4px;">
            <strong>GSTIN:</strong> ${pharmacy.gstin} | <strong>DL No:</strong> ${pharmacy.dlNo}
          </div>
        </td>
        <td style="vertical-align: top; text-align: right; width: 40%;">
          <div style="font-size: 22px; font-weight: 800; color: #1e293b;">RETAIL TAX INVOICE</div>
          <div style="margin-top: 4px; font-family: monospace; font-size: 14px; font-weight: 700; color: #0284c7;">
            ${invoice.invoice_no}
          </div>
          <div style="margin-top: 4px; color: #64748b; font-size: 11px;">
            Date: <strong>${invoiceDate}</strong>
          </div>
          <div style="margin-top: 6px;">
            <span class="badge">${(invoice.payment_status || 'PAID').toUpperCase()} • ${(invoice.payment_method || 'CASH').toUpperCase()}</span>
          </div>
        </td>
      </tr>
    </table>

    <!-- Customer & Prescribing Info -->
    <table class="details-box">
      <tr>
        <td style="width: 50%;">
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 2px;">Billed To (Patient / Customer)</div>
          <div style="font-size: 13px; font-weight: 700; color: #0f172a;">${customerName}</div>
          <div style="color: #475569; font-size: 11px; margin-top: 2px;">Phone: ${customerPhone}</div>
          <div style="color: #475569; font-size: 11px;">Address: ${customerAddress}</div>
        </td>
        <td style="width: 50%; border-left: 1px solid #e2e8f0;">
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 2px;">Prescription & Dispensing Staff</div>
          <div style="color: #475569; font-size: 11px;">Doctor / Prescription Ref: <strong>${doctorRef}</strong></div>
          <div style="color: #475569; font-size: 11px; margin-top: 2px;">Dispensed By: <strong>${cashierName}</strong></div>
          <div style="color: #64748b; font-size: 10px; margin-top: 2px;">Payment Terms: Immediate / Settled</div>
        </td>
      </tr>
    </table>

    <!-- Line Items Table -->
    <table class="items-table">
      <thead>
        <tr>
          <th style="width: 4%;">#</th>
          <th style="text-align: left; width: 36%;">Item Description</th>
          <th style="text-align: left; width: 16%;">Batch</th>
          <th style="text-align: left; width: 14%;">Expiry</th>
          <th style="text-align: center; width: 8%;">Qty</th>
          <th style="text-align: right; width: 10%;">Price</th>
          <th style="text-align: right; width: 12%;">Amount</th>
        </tr>
      </thead>
      <tbody>
        ${itemsRows}
      </tbody>
    </table>

    <!-- Financial Totals -->
    <table style="width: 100%; border-collapse: collapse;">
      <tr>
        <td style="width: 55%; vertical-align: top; padding-right: 20px;">
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 11px; color: #475569;">
            <strong>Statutory Terms & Patient Notice:</strong><br>
            • All schedules & antibiotics dispensed strictly against valid medical prescriptions.<br>
            • Store medicines below 25°C in a cool, dry place away from sunlight.<br>
            • Goods once sold can only be returned within 3 days in intact sealed packing.
          </div>
        </td>
        <td style="width: 45%; vertical-align: top;">
          <table class="totals-table">
            <tr>
              <td style="color: #64748b;">Items Subtotal:</td>
              <td style="font-weight: 600; width: 100px;">$${subtotal.toFixed(2)}</td>
            </tr>
            ${
              discount > 0
                ? `<tr>
                    <td style="color: #dc2626;">Promotional / Store Discount:</td>
                    <td style="font-weight: 600; color: #dc2626;">-$${discount.toFixed(2)}</td>
                  </tr>`
                : ''
            }
            <tr>
              <td style="color: #64748b;">Applicable Tax (GST Included):</td>
              <td style="font-weight: 500; color: #475569;">$0.00</td>
            </tr>
            <tr class="grand-total">
              <td>Net Payable Amount:</td>
              <td>$${netAmount.toFixed(2)}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <!-- Signatures -->
    <div class="sign-box">
      <div>
        <div class="sign-line">Customer Signature</div>
      </div>
      <div>
        <div class="sign-line">For MediShop Pharmacy (Pharmacist)</div>
      </div>
    </div>

    <!-- Footer Note -->
    <div class="footer">
      Thank you for trusting MediShop Healthcare! • Prompt recovery & good health.<br>
      This is a verified computer-generated tax invoice. No signature required for digital audit.
    </div>
  </div>
</body>
</html>`;
}

/**
 * Downloads a standalone HTML invoice file to the client machine.
 */
export function downloadInvoiceAsHtml(invoice) {
  if (!invoice) return;
  const html = generateInvoiceHtml(invoice);
  const blob = new Blob([html], { type: 'text/html;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `invoice_${invoice.invoice_no || 'receipt'}.html`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Opens a print dialog using a hidden iframe for seamless printing / PDF saving.
 */
export function printInvoiceDirectly(invoice) {
  if (!invoice) return;
  const html = generateInvoiceHtml(invoice);
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  document.body.appendChild(iframe);

  const doc = iframe.contentWindow || iframe.contentDocument;
  const d = doc.document || doc;
  d.open();
  d.write(html);
  d.close();

  iframe.contentWindow.focus();
  setTimeout(() => {
    iframe.contentWindow.print();
    setTimeout(() => {
      document.body.removeChild(iframe);
    }, 1000);
  }, 250);
}

