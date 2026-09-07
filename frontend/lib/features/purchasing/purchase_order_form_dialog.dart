import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';
import 'purchase_order_models.dart';

class PurchaseOrderFormDialog extends StatefulWidget {
  const PurchaseOrderFormDialog({super.key, required this.api, this.order});

  final ApiClient api;
  final PurchaseOrderModel? order;

  @override
  State<PurchaseOrderFormDialog> createState() =>
      _PurchaseOrderFormDialogState();
}

class _PurchaseOrderFormDialogState extends State<PurchaseOrderFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final _quotationReference = TextEditingController();
  final _paymentTerms = TextEditingController(text: '30');
  final _discount = TextEditingController(text: '0');
  final _ppn = TextEditingController(text: '0');
  final _pph23 = TextEditingController(text: '0');
  final _notes = TextEditingController();
  final List<_OrderItemDraft> _items = [];

  List<Map<String, dynamic>> _suppliers = [];
  List<Map<String, dynamic>> _plants = [];
  List<Map<String, dynamic>> _products = [];
  String? _supplierCode;
  String? _plantCode;
  late DateTime _poDate;
  late DateTime _deliveryDate;
  DateTime? _quotationDate;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final order = widget.order;
    final now = DateTime.now();
    _poDate = order?.poDate ?? DateTime(now.year, now.month, now.day);
    _deliveryDate =
        order?.requestedDeliveryDate ?? _poDate.add(const Duration(days: 7));
    _quotationDate = order?.quotationDate;
    _supplierCode = order?.supplierCode;
    _plantCode = order?.deliveryPlantCode;
    _quotationReference.text = order?.quotationReference ?? '';
    _paymentTerms.text = order?.paymentTermsDays.toString() ?? '30';
    _discount.text = order?.discountAmount.toString() ?? '0';
    _ppn.text = order?.ppnRate.toString() ?? '0';
    _pph23.text = order?.pph23Rate.toString() ?? '0';
    _notes.text = order?.notes ?? '';
    _loadLookups();
  }

  @override
  void dispose() {
    _quotationReference.dispose();
    _paymentTerms.dispose();
    _discount.dispose();
    _ppn.dispose();
    _pph23.dispose();
    _notes.dispose();
    for (final item in _items) {
      item.dispose();
    }
    super.dispose();
  }

  Future<void> _loadLookups() async {
    try {
      final responses = await Future.wait([
        widget.api.getJson(
          '/master-data/corporations?size=100&supplier_only=true',
        ),
        widget.api.getJson('/master-data/plants?size=100'),
      ]);
      if (!mounted) return;
      _suppliers = List<Map<String, dynamic>>.from(
        responses[0]['items'] as List,
      );
      _plants = List<Map<String, dynamic>>.from(responses[1]['items'] as List);
      if (_supplierCode != null) await _loadProducts(_supplierCode!);
      final existing = widget.order;
      if (existing != null) {
        for (final item in existing.items) {
          _items.add(_OrderItemDraft.fromModel(item));
        }
      } else {
        _items.add(_OrderItemDraft());
      }
    } on ApiException catch (exception) {
      _error = exception.message;
    } catch (_) {
      _error = 'Unable to load Purchasing form data.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadProducts(String supplierCode) async {
    final response = await widget.api.getJson(
      '/master-data/products?size=100&supplier_code=${Uri.encodeQueryComponent(supplierCode)}',
    );
    _products = List<Map<String, dynamic>>.from(response['items'] as List);
    if (mounted) setState(() {});
  }

  Future<void> _changeSupplier(String? code) async {
    if (code == null || code == _supplierCode) return;
    setState(() {
      _supplierCode = code;
      _products = [];
      for (final item in _items) {
        item.productCode = null;
      }
    });
    try {
      await _loadProducts(code);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  Future<DateTime?> _pickDate(DateTime initial) {
    return showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
    );
  }

  String _date(DateTime value) {
    String two(int number) => number.toString().padLeft(2, '0');
    return '${value.year}-${two(value.month)}-${two(value.day)}';
  }

  void _addItem() => setState(() => _items.add(_OrderItemDraft()));

  void _removeItem(int index) {
    if (_items.length == 1) return;
    setState(() => _items.removeAt(index).dispose());
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (!_formKey.currentState!.validate()) return;
    if (_supplierCode == null || _plantCode == null) {
      setState(() => _error = 'Supplier and Plant are required.');
      return;
    }
    final productCodes = _items.map((item) => item.productCode).toList();
    if (productCodes.any((code) => code == null)) {
      setState(() => _error = 'Select a Product for every item.');
      return;
    }
    if (productCodes.toSet().length != productCodes.length) {
      setState(() => _error = 'The same Product cannot be added twice.');
      return;
    }

    setState(() => _saving = true);
    final body = <String, dynamic>{
      'po_date': _date(_poDate),
      'supplier_code': _supplierCode,
      'quotation_reference': _quotationReference.text.trim().isEmpty
          ? null
          : _quotationReference.text.trim(),
      'quotation_date': _quotationDate == null ? null : _date(_quotationDate!),
      'requested_delivery_date': _date(_deliveryDate),
      'delivery_plant_code': _plantCode,
      'notes': _notes.text.trim(),
      'payment_terms_days': int.parse(_paymentTerms.text),
      'discount_amount': double.parse(_discount.text),
      'ppn_rate': double.parse(_ppn.text),
      'pph23_rate': double.parse(_pph23.text),
      'items': _items
          .map(
            (item) => {
              'product_code': item.productCode,
              'quantity_grams': double.parse(item.quantity.text),
              'unit': item.unit,
              'unit_price': double.parse(item.price.text),
              'remark': item.remark.text.trim(),
            },
          )
          .toList(),
    };
    try {
      if (widget.order == null) {
        await widget.api.postJson('/purchasing', body);
      } else {
        await widget.api.patchJson(
          '/purchasing/${widget.order!.poNumber}',
          body,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to save Purchase Order.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _positiveNumber(
    String? value,
    String label, {
    bool allowZero = false,
  }) {
    final parsed = double.tryParse(value ?? '');
    if (parsed == null || (allowZero ? parsed < 0 : parsed <= 0)) {
      return '$label must be ${allowZero ? 'zero or greater' : 'greater than zero'}';
    }
    return null;
  }

  String? _nonNegativeInteger(String? value, String label) {
    final parsed = int.tryParse(value ?? '');
    if (parsed == null || parsed < 0) return '$label must be a whole number';
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000, maxHeight: 850),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 18, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      widget.order == null
                          ? 'Create Purchase Order'
                          : 'Edit ${widget.order!.poNumber}',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: _saving ? null : () => Navigator.pop(context),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _form(),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving ? null : () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 10),
                  FilledButton.icon(
                    onPressed: _saving || _loading ? null : _submit,
                    icon: _saving
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.save_outlined),
                    label: const Text('Save as Waiting Review'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _form() {
    return Form(
      key: _formKey,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_error != null) ...[
              MaterialBanner(
                content: Text(_error!),
                actions: [
                  TextButton(
                    onPressed: () => setState(() => _error = null),
                    child: const Text('Close'),
                  ),
                ],
              ),
              const SizedBox(height: 16),
            ],
            Text(
              'PO Information',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                _fieldBox(
                  _dateField('PO Date', _poDate, (value) => _poDate = value),
                ),
                _fieldBox(
                  DropdownButtonFormField<String>(
                    initialValue: _supplierCode,
                    decoration: const InputDecoration(labelText: 'Supplier *'),
                    isExpanded: true,
                    items: _suppliers
                        .map(
                          (supplier) => DropdownMenuItem(
                            value: supplier['code'].toString(),
                            child: Text(
                              '${supplier['code']} — ${supplier['name']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: _changeSupplier,
                    validator: (value) =>
                        value == null ? 'Supplier is required' : null,
                  ),
                ),
                _fieldBox(
                  TextFormField(
                    controller: _quotationReference,
                    decoration: const InputDecoration(
                      labelText: 'Quotation Reference',
                    ),
                    validator: (value) =>
                        value != null &&
                            value.trim().isNotEmpty &&
                            _quotationDate == null
                        ? 'Select Quotation Date'
                        : null,
                  ),
                ),
                _fieldBox(
                  _dateField(
                    'Quotation Date',
                    _quotationDate,
                    (value) => _quotationDate = value,
                    optional: true,
                  ),
                ),
                _fieldBox(
                  _dateField(
                    'Requested Delivery Date',
                    _deliveryDate,
                    (value) => _deliveryDate = value,
                  ),
                ),
                _fieldBox(
                  DropdownButtonFormField<String>(
                    initialValue: _plantCode,
                    decoration: const InputDecoration(labelText: 'Plant *'),
                    isExpanded: true,
                    items: _plants
                        .map(
                          (plant) => DropdownMenuItem(
                            value: plant['code'].toString(),
                            child: Text(
                              '${plant['code']} — ${plant['name']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) => setState(() => _plantCode = value),
                    validator: (value) =>
                        value == null ? 'Plant is required' : null,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Order Items',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: _supplierCode == null ? null : _addItem,
                  icon: const Icon(Icons.add),
                  label: const Text('Add Item'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...List.generate(
              _items.length,
              (index) => _itemCard(index, _items[index]),
            ),
            const SizedBox(height: 20),
            Text(
              'Payment & Tax',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                _fieldBox(
                  TextFormField(
                    controller: _paymentTerms,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Payment Terms (days)',
                    ),
                    validator: (value) =>
                        _positiveNumber(
                          value,
                          'Payment terms',
                          allowZero: true,
                        ) ??
                        _nonNegativeInteger(value, 'Payment terms'),
                  ),
                ),
                _fieldBox(
                  _numberField(
                    _discount,
                    'Discount Amount (IDR)',
                    allowZero: true,
                  ),
                ),
                _fieldBox(_numberField(_ppn, 'PPN Rate (%)', allowZero: true)),
                _fieldBox(
                  _numberField(_pph23, 'PPh 23 Rate (%)', allowZero: true),
                ),
              ],
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _notes,
              minLines: 3,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'General Note'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _fieldBox(Widget child) => SizedBox(width: 285, child: child);

  Widget _numberField(
    TextEditingController controller,
    String label, {
    bool allowZero = false,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(labelText: label),
      validator: (value) => _positiveNumber(value, label, allowZero: allowZero),
    );
  }

  Widget _dateField(
    String label,
    DateTime? value,
    ValueChanged<DateTime> onChanged, {
    bool optional = false,
  }) {
    return InkWell(
      onTap: () async {
        final selected = await _pickDate(value ?? DateTime.now());
        if (selected != null) setState(() => onChanged(selected));
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: optional && value != null
              ? IconButton(
                  onPressed: () => setState(() => _quotationDate = null),
                  icon: const Icon(Icons.clear),
                )
              : const Icon(Icons.calendar_today_outlined),
        ),
        child: Text(value == null ? '-' : _date(value)),
      ),
    );
  }

  Widget _itemCard(int index, _OrderItemDraft item) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Item ${index + 1}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                IconButton(
                  onPressed: _items.length == 1
                      ? null
                      : () => _removeItem(index),
                  icon: const Icon(Icons.delete_outline),
                  color: Theme.of(context).colorScheme.error,
                ),
              ],
            ),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                SizedBox(
                  width: 310,
                  child: DropdownButtonFormField<String>(
                    initialValue: item.productCode,
                    decoration: const InputDecoration(labelText: 'Product *'),
                    isExpanded: true,
                    items: _products
                        .map(
                          (product) => DropdownMenuItem(
                            value: product['code'].toString(),
                            child: Text(
                              '${product['code']} — ${product['description']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => item.productCode = value),
                    validator: (value) =>
                        value == null ? 'Product is required' : null,
                  ),
                ),
                SizedBox(
                  width: 180,
                  child: _numberField(item.quantity, 'Quantity'),
                ),
                SizedBox(
                  width: 150,
                  child: DropdownButtonFormField<String>(
                    initialValue: item.unit,
                    decoration: const InputDecoration(labelText: 'Unit'),
                    items: inventoryUnits
                        .map(
                          (unit) => DropdownMenuItem(
                            value: unit,
                            child: Text(unitLabel(unit)),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => item.unit = value ?? 'pcs'),
                  ),
                ),
                SizedBox(
                  width: 210,
                  child: _numberField(
                    item.price,
                    'Unit Price (IDR)',
                    allowZero: true,
                  ),
                ),
                SizedBox(
                  width: 260,
                  child: TextFormField(
                    controller: item.remark,
                    decoration: const InputDecoration(labelText: 'Remark'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _OrderItemDraft {
  _OrderItemDraft({
    this.productCode,
    String quantity = '',
    String price = '',
    String remark = '',
    this.unit = 'pcs',
  }) : quantity = TextEditingController(text: quantity),
       price = TextEditingController(text: price),
       remark = TextEditingController(text: remark);

  factory _OrderItemDraft.fromModel(PurchaseOrderItemModel item) {
    return _OrderItemDraft(
      productCode: item.productCode,
      quantity: item.quantityGrams.toString(),
      price: item.unitPrice.toString(),
      remark: item.remark,
      unit: item.unit,
    );
  }

  String? productCode;
  String unit;
  final TextEditingController quantity;
  final TextEditingController price;
  final TextEditingController remark;

  void dispose() {
    quantity.dispose();
    price.dispose();
    remark.dispose();
  }
}
