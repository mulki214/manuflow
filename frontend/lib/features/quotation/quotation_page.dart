import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/modal_widgets.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';

class QuotationPage extends StatefulWidget {
  const QuotationPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<QuotationPage> createState() => _QuotationPageState();
}

class _QuotationPageState extends State<QuotationPage> {
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _customers = [];
  List<Map<String, dynamic>> _products = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.auth.api.getJson('/quotations?size=100'),
        widget.auth.api.getJson(
          '/master-data/corporations?size=100&customer_only=true',
        ),
        widget.auth.api.getJson('/master-data/products?size=100'),
      ]);
      if (!mounted) return;
      setState(() {
        _items = (values[0]['items'] as List).cast<Map<String, dynamic>>();
        _customers = (values[1]['items'] as List).cast<Map<String, dynamic>>();
        _products = (values[2]['items'] as List).cast<Map<String, dynamic>>();
        _error = null;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _download(Map<String, dynamic> item) async {
    try {
      final number = item['quotation_number'].toString();
      final bytes = await widget.auth.api.getBytes(
        '/quotations/${Uri.encodeComponent(number)}/pdf',
      );
      await FileSaver.instance.saveFile(
        name: 'quotation-$number',
        bytes: bytes,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    final number = item['quotation_number'].toString();
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete Quotation?'),
            content: Text('Delete $number?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;
    try {
      await widget.auth.api.delete(
        '/quotations/${Uri.encodeComponent(number)}',
      );
      await _load();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _form({Map<String, dynamic>? existing}) async {
    var date =
        DateTime.tryParse(existing?['quotation_date']?.toString() ?? '') ??
        DateTime.now();
    var validUntil =
        DateTime.tryParse(existing?['valid_until']?.toString() ?? '') ??
        date.add(const Duration(days: 30));
    String? customerCode = existing?['customer_code']?.toString();
    final discount = TextEditingController(
      text: existing?['discount_amount']?.toString() ?? '0',
    );
    final taxLabel = TextEditingController(
      text: existing?['tax_label']?.toString() ?? 'PPN',
    );
    final taxRate = TextEditingController(
      text: existing?['tax_rate']?.toString() ?? '0',
    );
    final notes = TextEditingController(
      text: existing?['notes']?.toString() ?? '',
    );
    final paymentTerms = TextEditingController(
      text: existing?['payment_terms']?.toString() ?? '',
    );
    final lines = ((existing?['items'] as List?) ?? const [])
        .map((value) => _QuoteLine.fromJson(value as Map<String, dynamic>))
        .toList();
    if (lines.isEmpty) lines.add(_QuoteLine());
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          final subtotal = lines.fold<double>(
            0,
            (sum, line) => sum + line.amount,
          );
          final discountValue = double.tryParse(discount.text) ?? 0;
          final tax =
              (subtotal - discountValue).clamp(0, double.infinity) *
              (double.tryParse(taxRate.text) ?? 0) /
              100;
          return AlertDialog(
            title: Text(
              existing == null
                  ? 'Create Quotation'
                  : 'Edit ${existing['quotation_number']}',
            ),
            content: SizedBox(
              width: 720,
              child: ModalScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButtonFormField<String>(
                      initialValue: customerCode,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Customer *',
                      ),
                      items: _customers
                          .map(
                            (customer) => DropdownMenuItem(
                              value: customer['code'].toString(),
                              child: Text(
                                '${customer['code']} - ${customer['name']}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) =>
                          setDialogState(() => customerCode = value),
                    ),
                    const SizedBox(height: 10),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Quotation Date'),
                      subtitle: Text(_date(date)),
                      trailing: const Icon(Icons.calendar_today_outlined),
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: date,
                          firstDate: DateTime(2020),
                          lastDate: DateTime(2200),
                        );
                        if (picked != null) {
                          setDialogState(() {
                            date = picked;
                            if (validUntil.isBefore(date)) validUntil = date;
                          });
                        }
                      },
                    ),
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Valid Until'),
                      subtitle: Text(_date(validUntil)),
                      trailing: const Icon(Icons.calendar_today_outlined),
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: validUntil,
                          firstDate: date,
                          lastDate: DateTime(2200),
                        );
                        if (picked != null) {
                          setDialogState(() => validUntil = picked);
                        }
                      },
                    ),
                    const Divider(),
                    const Text(
                      'Quotation Items',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    ...lines.asMap().entries.map(
                      (entry) => _lineEditor(
                        entry.key,
                        entry.value,
                        setDialogState,
                        lines,
                      ),
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        onPressed: () =>
                            setDialogState(() => lines.add(_QuoteLine())),
                        icon: const Icon(Icons.add),
                        label: const Text('Add Product'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: discount,
                            keyboardType: TextInputType.number,
                            onChanged: (_) => setDialogState(() {}),
                            decoration: const InputDecoration(
                              labelText: 'Discount Amount',
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: TextField(
                            controller: taxLabel,
                            decoration: const InputDecoration(
                              labelText: 'Tax Label',
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        SizedBox(
                          width: 120,
                          child: TextField(
                            controller: taxRate,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            onChanged: (_) => setDialogState(() {}),
                            decoration: const InputDecoration(
                              labelText: 'Tax %',
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Subtotal: IDR ${subtotal.toStringAsFixed(2)}\nTax: IDR ${tax.toStringAsFixed(2)}\nGrand Total: IDR ${(subtotal - discountValue + tax).toStringAsFixed(2)}',
                      textAlign: TextAlign.right,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: paymentTerms,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Payment Terms',
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: notes,
                      maxLines: 3,
                      decoration: const InputDecoration(labelText: 'Notes'),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () async {
                  if (customerCode == null ||
                      lines.any((line) => !line.complete)) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Select a customer and complete every item.',
                        ),
                      ),
                    );
                    return;
                  }
                  final body = {
                    'quotation_date': _apiDate(date),
                    'valid_until': _apiDate(validUntil),
                    'customer_code': customerCode,
                    'discount_amount': discount.text,
                    'tax_label': taxLabel.text.trim().isEmpty
                        ? 'PPN'
                        : taxLabel.text.trim(),
                    'tax_rate': taxRate.text,
                    'payment_terms': paymentTerms.text.trim(),
                    'notes': notes.text.trim(),
                    'items': lines.map((line) => line.toJson()).toList(),
                  };
                  try {
                    if (existing == null) {
                      await widget.auth.api.postJson('/quotations', body);
                    } else {
                      await widget.auth.api.patchJson(
                        '/quotations/${existing['quotation_number']}',
                        body,
                      );
                    }
                    if (context.mounted) {
                      Navigator.pop(context, true);
                    }
                  } on ApiException catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(e.message)));
                    }
                  }
                },
                child: const Text('Save'),
              ),
            ],
          );
        },
      ),
    );
    discount.dispose();
    taxLabel.dispose();
    taxRate.dispose();
    notes.dispose();
    paymentTerms.dispose();
    for (final line in lines) {
      line.dispose();
    }
    if (saved == true) await _load();
  }

  Widget _lineEditor(
    int index,
    _QuoteLine line,
    StateSetter setState,
    List<_QuoteLine> lines,
  ) => Card(
    child: Padding(
      padding: const EdgeInsets.all(10),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Product ${index + 1}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              if (lines.length > 1)
                IconButton(
                  onPressed: () => setState(() {
                    line.dispose();
                    lines.removeAt(index);
                  }),
                  icon: const Icon(Icons.delete_outline),
                ),
            ],
          ),
          DropdownButtonFormField<String>(
            initialValue: line.productCode,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Product *'),
            items: _products
                .map(
                  (product) => DropdownMenuItem(
                    value: product['code'].toString(),
                    child: Text(
                      '${product['part_name']} - ${product['description']}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: (code) => setState(() {
              line.productCode = code;
              line.unit = line.unit ?? 'pcs';
            }),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: line.quantity,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(labelText: 'Quantity *'),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 120,
                child: DropdownButtonFormField<String>(
                  initialValue: line.unit,
                  decoration: const InputDecoration(labelText: 'Unit *'),
                  items: inventoryUnits
                      .map(
                        (unit) => DropdownMenuItem(
                          value: unit,
                          child: Text(unitLabel(unit)),
                        ),
                      )
                      .toList(),
                  onChanged: (value) => setState(() => line.unit = value),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: line.unitPrice,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(labelText: 'Unit Price *'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: line.remark,
            decoration: const InputDecoration(labelText: 'Remark'),
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.quotation,
    title: 'Quotation',
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _form(),
      icon: const Icon(Icons.add),
      label: const Text('Create Quotation'),
    ),
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quotations',
            style: Theme.of(
              context,
            ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            '${_items.length} quotation records',
            style: const TextStyle(color: Color(0xFF667085)),
          ),
          const SizedBox(height: 18),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(child: Text(_error!))
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView.separated(
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, index) {
                        final item = _items[index];
                        return Card(
                          child: ListTile(
                            onTap: () => _form(existing: item),
                            title: Text(
                              '${item['quotation_number']} - ${item['customer_name']}',
                            ),
                            subtitle: Text(
                              '${item['quotation_date']} • Valid until ${item['valid_until']}\n${(item['items'] as List).length} product(s) • IDR ${item['grand_total']}',
                            ),
                            isThreeLine: true,
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: 'Download PDF',
                                  onPressed: () => _download(item),
                                  icon: const Icon(
                                    Icons.picture_as_pdf_outlined,
                                  ),
                                ),
                                IconButton(
                                  tooltip: 'Delete',
                                  onPressed: () => _delete(item),
                                  icon: const Icon(
                                    Icons.delete_outline,
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

class _QuoteLine {
  _QuoteLine({
    this.productCode,
    this.unit = 'pcs',
    String quantity = '',
    String unitPrice = '',
    String remark = '',
  }) : quantity = TextEditingController(text: quantity),
       unitPrice = TextEditingController(text: unitPrice),
       remark = TextEditingController(text: remark);
  factory _QuoteLine.fromJson(Map<String, dynamic> json) => _QuoteLine(
    productCode: json['product_code']?.toString(),
    unit: json['unit']?.toString() ?? 'pcs',
    quantity: json['quantity']?.toString() ?? '',
    unitPrice: json['unit_price']?.toString() ?? '',
    remark: json['remark']?.toString() ?? '',
  );
  String? productCode;
  String? unit;
  final TextEditingController quantity;
  final TextEditingController unitPrice;
  final TextEditingController remark;
  bool get complete =>
      productCode != null &&
      unit != null &&
      (double.tryParse(quantity.text) ?? 0) > 0 &&
      (double.tryParse(unitPrice.text) ?? -1) >= 0;
  double get amount =>
      (double.tryParse(quantity.text) ?? 0) *
      (double.tryParse(unitPrice.text) ?? 0);
  Map<String, dynamic> toJson() => {
    'product_code': productCode,
    'quantity': quantity.text,
    'unit': unit,
    'unit_price': unitPrice.text,
    'remark': remark.text.trim(),
  };
  void dispose() {
    quantity.dispose();
    unitPrice.dispose();
    remark.dispose();
  }
}

String _apiDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
String _date(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
