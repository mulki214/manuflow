import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/modal_widgets.dart';
import '../../shared/searchable_select_field.dart';
import '../auth/auth_controller.dart';

class InvoicePage extends StatefulWidget {
  const InvoicePage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<InvoicePage> createState() => _InvoicePageState();
}

class _InvoicePageState extends State<InvoicePage> {
  List<Map<String, dynamic>> _invoices = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final invoices = <Map<String, dynamic>>[];
      var page = 1;
      var total = 0;
      do {
        final result = await widget.auth.api.getJson(
          '/invoices?page=$page&size=100',
        );
        invoices.addAll((result['items'] as List).cast<Map<String, dynamic>>());
        total = result['total'] as int;
        page++;
      } while (invoices.length < total);
      if (!mounted) return;
      setState(() {
        _invoices = invoices;
        _error = null;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _download(Map<String, dynamic> invoice) async {
    final number = invoice['invoice_number'].toString();
    try {
      final bytes = await widget.auth.api.getBytes(
        '/invoices/${Uri.encodeComponent(number)}/pdf',
      );
      await FileSaver.instance.saveFile(
        name: 'invoice-$number',
        bytes: bytes,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
    } on ApiException catch (error) {
      _message(error.message);
    }
  }

  Future<void> _void(Map<String, dynamic> invoice) async {
    final reason = TextEditingController();
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Void ${invoice['invoice_number']}?'),
        content: TextField(
          controller: reason,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Reason *'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Void invoice'),
          ),
        ],
      ),
    );
    final value = reason.text.trim();
    reason.dispose();
    if (accepted != true) return;
    if (value.length < 3) {
      _message('Enter a reason with at least 3 characters.');
      return;
    }
    try {
      await widget.auth.api.postJson(
        '/invoices/${Uri.encodeComponent(invoice['invoice_number'].toString())}/void',
        {'reason': value},
      );
      await _load();
    } on ApiException catch (error) {
      _message(error.message);
    }
  }

  void _message(String message) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> _create() async {
    List<Map<String, dynamic>> salesOrders;
    try {
      salesOrders =
          (await widget.auth.api.getJson('/invoices/eligible-sales-orders')
                  as List)
              .cast<Map<String, dynamic>>();
    } on ApiException catch (error) {
      _message(error.message);
      return;
    }
    if (!mounted) return;
    if (salesOrders.isEmpty) {
      _message('No Sales Order has delivered quantities available to invoice.');
      return;
    }
    final deliveries = <Map<String, dynamic>>[];
    final selected = <String, _InvoiceSelection>{};
    final taxLabel = TextEditingController(text: 'PPN');
    final taxRate = TextEditingController(text: '0');
    final discount = TextEditingController(text: '0');
    final paymentTerms = TextEditingController();
    final notes = TextEditingController();
    var invoiceDate = DateTime.now();
    DateTime? dueDate;
    String? selectedSalesOrderNumber;
    bool loadingDeliveries = false;
    String? deliveryError;
    var deliveryLoadGeneration = 0;
    final created = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          final subtotal = selected.values.fold<double>(
            0,
            (sum, value) => sum + value.amount,
          );
          final discountValue = double.tryParse(discount.text) ?? 0;
          final taxable = (subtotal - discountValue).clamp(0, double.infinity);
          final tax = taxable * (double.tryParse(taxRate.text) ?? 0) / 100;
          final total = taxable + tax;
          final options = deliveries;
          return AlertDialog(
            title: const Text('Create Invoice'),
            content: SizedBox(
              width: 860,
              child: ModalScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Choose the Sales Order first, then select delivered quantities to combine into this invoice.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 12),
                    SearchableSelectField<String>(
                      value: selectedSalesOrderNumber,
                      labelText: 'Sales Order *',
                      searchHint: 'Search Sales Order or customer',
                      options: salesOrders.map((order) {
                        final number = order['sales_order_number'].toString();
                        final customerCode = order['customer_code'].toString();
                        final customerName = order['customer_name'].toString();
                        return SearchableSelectOption<String>(
                          value: number,
                          label: '$number — $customerName',
                          searchTerms: [customerCode, customerName],
                        );
                      }).toList(),
                      onChanged: (value) async {
                        final generation = ++deliveryLoadGeneration;
                        setDialogState(() {
                          selectedSalesOrderNumber = value;
                          selected.clear();
                          deliveries.clear();
                          deliveryError = null;
                          loadingDeliveries = value != null;
                        });
                        if (value == null) return;
                        final selectedDeliveries = <Map<String, dynamic>>[];
                        try {
                          var page = 1;
                          var total = 0;
                          do {
                            final response = await widget.auth.api.getJson(
                              '/invoices/eligible-deliveries?sales_order_number=${Uri.encodeQueryComponent(value)}&page=$page&size=200',
                            );
                            selectedDeliveries.addAll(
                              (response['items'] as List)
                                  .cast<Map<String, dynamic>>(),
                            );
                            total = response['total_deliveries'] as int;
                            page++;
                          } while ((page - 1) * 200 < total);
                          if (generation != deliveryLoadGeneration) return;
                          setDialogState(() {
                            deliveries.addAll(selectedDeliveries);
                            loadingDeliveries = false;
                          });
                        } on ApiException catch (error) {
                          if (generation != deliveryLoadGeneration) return;
                          setDialogState(() {
                            deliveryError = error.message;
                            loadingDeliveries = false;
                          });
                        }
                      },
                    ),
                    if (selectedSalesOrderNumber == null)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text(
                          'Select a Sales Order to view its delivered items.',
                        ),
                      ),
                    if (loadingDeliveries)
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(child: CircularProgressIndicator()),
                      ),
                    if (deliveryError != null)
                      Text(
                        deliveryError!,
                        style: const TextStyle(color: Colors.red),
                      ),
                    if (selectedSalesOrderNumber != null &&
                        !loadingDeliveries &&
                        deliveryError == null &&
                        deliveries.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: Text(
                          'No delivered quantities remain available for this Sales Order.',
                        ),
                      ),
                    OutlinedButton.icon(
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: invoiceDate,
                          firstDate: DateTime(2000),
                          lastDate: DateTime(2100),
                        );
                        if (picked != null) {
                          setDialogState(() => invoiceDate = picked);
                        }
                      },
                      icon: const Icon(Icons.calendar_today_outlined),
                      label: Text('Invoice date: ${_date(invoiceDate)}'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: dueDate ?? invoiceDate,
                          firstDate: invoiceDate,
                          lastDate: DateTime(2100),
                        );
                        if (picked != null) {
                          setDialogState(() => dueDate = picked);
                        }
                      },
                      icon: const Icon(Icons.event_outlined),
                      label: Text(
                        dueDate == null
                            ? 'Due date (optional)'
                            : 'Due date: ${_date(dueDate!)}',
                      ),
                    ),
                    const SizedBox(height: 8),
                    ...options.map((item) {
                      final key = _key(item);
                      final existing = selected[key];
                      final max = _number(item['available_quantity']);
                      final qty = existing?.quantity ?? max;
                      return Card(
                        child: CheckboxListTile(
                          value: existing != null,
                          onChanged: (checked) => setDialogState(() {
                            if (checked == true) {
                              selected[key] = _InvoiceSelection(item, max);
                            } else {
                              selected.remove(key);
                            }
                          }),
                          title: Text(
                            '${item['part_name']} • ${item['product_code']}',
                          ),
                          subtitle: Text(
                            '${item['delivery_number']} • ${item['sales_order_number']} • Lot ${item['lot_number']}\nAvailable ${_formatQty(max)} ${item['unit']} • IDR ${item['unit_price']} / ${item['unit']}',
                          ),
                          secondary: existing == null
                              ? null
                              : SizedBox(
                                  width: 90,
                                  child: TextFormField(
                                    key: ValueKey('qty-$key'),
                                    initialValue: _formatQty(qty),
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                          decimal: true,
                                        ),
                                    decoration: const InputDecoration(
                                      labelText: 'Qty',
                                    ),
                                    onChanged: (text) => setDialogState(
                                      () => existing.quantity = _number(
                                        text,
                                      ).clamp(0.001, max),
                                    ),
                                  ),
                                ),
                          isThreeLine: true,
                        ),
                      );
                    }),
                    const Divider(),
                    Wrap(
                      spacing: 12,
                      runSpacing: 8,
                      children: [
                        SizedBox(
                          width: 180,
                          child: TextField(
                            controller: discount,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Discount (IDR)',
                            ),
                            onChanged: (_) => setDialogState(() {}),
                          ),
                        ),
                        SizedBox(
                          width: 160,
                          child: TextField(
                            controller: taxLabel,
                            decoration: const InputDecoration(
                              labelText: 'Tax label',
                            ),
                            onChanged: (_) => setDialogState(() {}),
                          ),
                        ),
                        SizedBox(
                          width: 140,
                          child: TextField(
                            controller: taxRate,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Tax %',
                            ),
                            onChanged: (_) => setDialogState(() {}),
                          ),
                        ),
                        SizedBox(
                          width: 240,
                          child: TextField(
                            controller: paymentTerms,
                            decoration: const InputDecoration(
                              labelText: 'Payment terms',
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: notes,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(labelText: 'Notes'),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Subtotal IDR ${_money(subtotal)}   •   Tax IDR ${_money(tax)}   •   Total IDR ${_money(total)}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: loadingDeliveries
                    ? null
                    : () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton.icon(
                onPressed:
                    selected.isEmpty ||
                        selectedSalesOrderNumber == null ||
                        loadingDeliveries
                    ? null
                    : () => Navigator.pop(context, true),
                icon: const Icon(Icons.receipt_long_outlined),
                label: const Text('Issue Invoice'),
              ),
            ],
          );
        },
      ),
    );
    if (created != true) {
      for (final controller in [
        taxLabel,
        taxRate,
        discount,
        paymentTerms,
        notes,
      ]) {
        controller.dispose();
      }
      return;
    }
    final discountAmount = _number(discount.text);
    if (discountAmount >
        selected.values.fold<double>(0, (sum, value) => sum + value.amount)) {
      _message('Discount cannot exceed invoice subtotal.');
      for (final controller in [
        taxLabel,
        taxRate,
        discount,
        paymentTerms,
        notes,
      ]) {
        controller.dispose();
      }
      return;
    }
    try {
      await widget.auth.api.postJson('/invoices', {
        'invoice_date': _date(invoiceDate),
        'sales_order_number': selectedSalesOrderNumber,
        'due_date': dueDate == null ? null : _date(dueDate!),
        'discount_amount': discountAmount,
        'tax_label': taxLabel.text.trim().isEmpty
            ? 'Tax'
            : taxLabel.text.trim(),
        'tax_rate': _number(taxRate.text),
        'payment_terms': paymentTerms.text.trim(),
        'notes': notes.text.trim(),
        'items': selected.values
            .map(
              (selection) => {
                'delivery_number': selection.data['delivery_number'],
                'delivery_line_id': selection.data['delivery_line_id'],
                'sales_order_item_id': selection.data['sales_order_item_id'],
                'quantity': selection.quantity,
              },
            )
            .toList(),
      });
      await _load();
      _message('Invoice issued.');
    } on ApiException catch (error) {
      _message(error.message);
    } finally {
      for (final controller in [
        taxLabel,
        taxRate,
        discount,
        paymentTerms,
        notes,
      ]) {
        controller.dispose();
      }
    }
  }

  String _key(Map<String, dynamic> item) =>
      '${item['delivery_number']}:${item['delivery_line_id'] ?? 'legacy-${item['sales_order_item_id']}'}';
  static double _number(dynamic value) =>
      double.tryParse(value?.toString() ?? '') ?? 0;
  static String _date(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  static String _formatQty(double value) => value == value.roundToDouble()
      ? value.toStringAsFixed(0)
      : value.toString();
  static String _money(double value) => value.toStringAsFixed(2);

  Future<void> _detail(Map<String, dynamic> invoice) async {
    final items = (invoice['items'] as List).cast<Map<String, dynamic>>();
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          '${invoice['invoice_number']} • ${invoice['customer_name']}',
        ),
        content: SizedBox(
          width: 680,
          child: ModalScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'SO ${invoice['sales_order_number']} • Date ${invoice['invoice_date']} • Due ${invoice['due_date'] ?? '-'} • ${invoice['status']}',
                ),
                const Divider(),
                ...items.map(
                  (item) => ListTile(
                    dense: true,
                    title: Text(
                      '${item['part_name']} (${item['product_code']})',
                    ),
                    subtitle: Text(
                      '${item['delivery_number']} • ${item['sales_order_number']} • Lot ${item['lot_number']}',
                    ),
                    trailing: Text(
                      '${item['quantity']} ${item['unit']}\nIDR ${item['amount']}',
                    ),
                  ),
                ),
                const Divider(),
                Text(
                  'Subtotal IDR ${invoice['subtotal']} • ${invoice['tax_label']} ${invoice['tax_rate']}%: IDR ${invoice['tax_amount']}\nGrand total IDR ${invoice['grand_total']}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                if ((invoice['void_reason'] ?? '').toString().isNotEmpty)
                  Text('Void reason: ${invoice['void_reason']}'),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.invoice,
    title: 'Invoice',
    floatingActionButton: FloatingActionButton.extended(
      onPressed: _create,
      icon: const Icon(Icons.add),
      label: const Text('Create Invoice'),
    ),
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Invoices',
            style: Theme.of(
              context,
            ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            '${_invoices.length} invoice records',
            style: const TextStyle(color: Color(0xFF667085)),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(child: Text(_error!))
                : RefreshIndicator(
                    onRefresh: _load,
                    child: _invoices.isEmpty
                        ? ListView(
                            children: const [
                              SizedBox(height: 140),
                              Center(child: Text('No invoices yet.')),
                            ],
                          )
                        : ListView.separated(
                            itemCount: _invoices.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (_, index) {
                              final invoice = _invoices[index];
                              final status = invoice['status'].toString();
                              return Card(
                                child: ListTile(
                                  onTap: () => _detail(invoice),
                                  title: Text(
                                    '${invoice['invoice_number']} • ${invoice['customer_name']}',
                                  ),
                                  subtitle: Text(
                                    'SO ${invoice['sales_order_number']} • ${invoice['invoice_date']} • ${(invoice['items'] as List).length} shipped item(s) • IDR ${invoice['grand_total']}\n${status == 'void' ? 'VOID • ${invoice['void_reason'] ?? ''}' : 'Due ${invoice['due_date'] ?? '-'}'}',
                                  ),
                                  isThreeLine: true,
                                  trailing: Wrap(
                                    spacing: 0,
                                    children: [
                                      IconButton(
                                        tooltip: 'Download PDF',
                                        onPressed: () => _download(invoice),
                                        icon: const Icon(
                                          Icons.picture_as_pdf_outlined,
                                        ),
                                      ),
                                      if (status == 'issued')
                                        IconButton(
                                          tooltip: 'Void invoice',
                                          onPressed: () => _void(invoice),
                                          icon: const Icon(
                                            Icons.block_outlined,
                                            color: Colors.red,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
          ),
        ],
      ),
    ),
  );
}

class _InvoiceSelection {
  _InvoiceSelection(this.data, this.quantity);
  final Map<String, dynamic> data;
  double quantity;
  double get amount => quantity * _InvoicePageState._number(data['unit_price']);
}
