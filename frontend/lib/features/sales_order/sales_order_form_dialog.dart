import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';
import 'sales_order_models.dart';

class SalesOrderFormDialog extends StatefulWidget {
  const SalesOrderFormDialog({super.key, required this.api, this.order});

  final ApiClient api;
  final SalesOrderModel? order;

  @override
  State<SalesOrderFormDialog> createState() => _SalesOrderFormDialogState();
}

class _SalesOrderFormDialogState extends State<SalesOrderFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final _customerPoNumber = TextEditingController();
  final _shipToName = TextEditingController();
  final _shipToAddress = TextEditingController();
  final _shipToContact = TextEditingController();
  final _shipToPhone = TextEditingController();
  final _notes = TextEditingController();
  final List<_SalesItemDraft> _items = [];

  List<Map<String, dynamic>> _customers = [];
  List<Map<String, dynamic>> _products = [];
  String? _customerCode;
  String _orderType = 'mass_pro';
  late DateTime _poReceiptDate;
  late DateTime _customerPoDate;
  late DateTime _deliveryDate;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final order = widget.order;
    final today = DateTime.now();
    _poReceiptDate =
        order?.poReceiptDate ?? DateTime(today.year, today.month, today.day);
    _customerPoDate = order?.customerPoDate ?? _poReceiptDate;
    _deliveryDate =
        order?.deliveryDate ?? _poReceiptDate.add(const Duration(days: 7));
    _customerCode = order?.customerCode;
    _orderType = order?.orderType ?? 'mass_pro';
    _customerPoNumber.text = order?.customerPoNumber ?? '';
    _shipToName.text = order?.shipToName ?? '';
    _shipToAddress.text = order?.shipToAddress ?? '';
    _shipToContact.text = order?.shipToContactPerson ?? '';
    _shipToPhone.text = order?.shipToPhone ?? '';
    _notes.text = order?.notes ?? '';
    _loadLookups();
  }

  @override
  void dispose() {
    for (final controller in [
      _customerPoNumber,
      _shipToName,
      _shipToAddress,
      _shipToContact,
      _shipToPhone,
      _notes,
    ]) {
      controller.dispose();
    }
    for (final item in _items) {
      item.dispose();
    }
    super.dispose();
  }

  Future<void> _loadLookups() async {
    try {
      final response = await widget.api.getJson(
        '/master-data/corporations?size=100&customer_only=true',
      );
      _customers = List<Map<String, dynamic>>.from(response['items'] as List);
      if (_customerCode != null) await _loadProducts(_customerCode!);
      if (widget.order == null) {
        _items.add(_SalesItemDraft());
      } else {
        _items.addAll(widget.order!.items.map(_SalesItemDraft.fromModel));
      }
    } on ApiException catch (exception) {
      _error = exception.message;
    } catch (_) {
      _error = 'Unable to load Sales Order form data.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadProducts(String customerCode) async {
    final response = await widget.api.getJson(
      '/master-data/products?size=100&customer_code=${Uri.encodeQueryComponent(customerCode)}',
    );
    _products = List<Map<String, dynamic>>.from(response['items'] as List);
    if (mounted) setState(() {});
  }

  Future<void> _changeCustomer(String? code) async {
    if (code == null || code == _customerCode) return;
    setState(() {
      _customerCode = code;
      _products = [];
      for (final item in _items) {
        item.productCode = null;
      }
    });
    try {
      await _loadProducts(code);
      final customer = _customers.firstWhere((item) => item['code'] == code);
      if (_shipToName.text.isEmpty) {
        _shipToName.text = customer['name'].toString();
      }
      if (_shipToAddress.text.isEmpty) {
        _shipToAddress.text = customer['address'].toString();
      }
      if (_shipToContact.text.isEmpty) {
        _shipToContact.text = customer['contact_person_name'].toString();
      }
      if (_shipToPhone.text.isEmpty) {
        _shipToPhone.text = customer['contact_person_phone'].toString();
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  Future<DateTime?> _pickDate(DateTime initial) => showDatePicker(
    context: context,
    initialDate: initial,
    firstDate: DateTime(2020),
    lastDate: DateTime(2200),
  );

  String _date(DateTime value) {
    String two(int number) => number.toString().padLeft(2, '0');
    return '${value.year}-${two(value.month)}-${two(value.day)}';
  }

  Future<void> _submit() async {
    setState(() => _error = null);
    if (!_formKey.currentState!.validate()) return;
    if (_customerCode == null ||
        _items.any((item) => item.productCode == null)) {
      setState(() => _error = 'Customer and Product are required.');
      return;
    }
    final products = _items.map((item) => item.productCode).toList();
    if (products.toSet().length != products.length) {
      setState(() => _error = 'The same Product cannot be added twice.');
      return;
    }
    setState(() => _saving = true);
    final body = {
      'po_receipt_date': _date(_poReceiptDate),
      'customer_po_date': _date(_customerPoDate),
      'customer_po_number': _customerPoNumber.text.trim(),
      'customer_code': _customerCode,
      'ship_to_name': _optional(_shipToName),
      'ship_to_address': _optional(_shipToAddress),
      'ship_to_contact_person': _optional(_shipToContact),
      'ship_to_phone': _optional(_shipToPhone),
      'delivery_date': _date(_deliveryDate),
      'order_type': _orderType,
      'notes': _notes.text.trim(),
      'items': _items
          .map(
            (item) => {
              'product_code': item.productCode,
              'quantity_grams': double.parse(item.quantity.text),
              'unit': item.unit,
              'unit_price': double.parse(item.price.text),
              'remark': item.remark.text.trim(),
              'outstanding_note': item.outstandingNote.text.trim(),
            },
          )
          .toList(),
    };
    try {
      if (widget.order == null) {
        await widget.api.postJson('/sales-orders', body);
      } else {
        await widget.api.patchJson(
          '/sales-orders/${widget.order!.salesOrderNumber}',
          body,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to save Sales Order.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _optional(TextEditingController controller) =>
      controller.text.trim().isEmpty ? null : controller.text.trim();

  String? _required(String? value) =>
      value == null || value.trim().isEmpty ? 'This field is required' : null;

  String? _number(String? value, String label, {bool allowZero = false}) {
    final parsed = double.tryParse(value ?? '');
    if (parsed == null || (allowZero ? parsed < 0 : parsed <= 0)) {
      return '$label must be ${allowZero ? 'zero or greater' : 'greater than zero'}';
    }
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
                          ? 'Create Sales Order'
                          : 'Edit ${widget.order!.salesOrderNumber}',
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
                    onPressed: _saving ? null : _submit,
                    icon: const Icon(Icons.save_outlined),
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

  Widget _form() => Form(
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
            'Sales Order Header',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 16,
            runSpacing: 16,
            children: [
              _box(
                _dateField(
                  'PO Receipt Date',
                  _poReceiptDate,
                  (date) => _poReceiptDate = date,
                ),
              ),
              _box(
                _dateField(
                  'Customer PO Date',
                  _customerPoDate,
                  (date) => _customerPoDate = date,
                ),
              ),
              _box(
                TextFormField(
                  controller: _customerPoNumber,
                  decoration: const InputDecoration(
                    labelText: 'Customer PO Number *',
                  ),
                  validator: _required,
                ),
              ),
              _box(
                DropdownButtonFormField<String>(
                  initialValue: _customerCode,
                  decoration: const InputDecoration(labelText: 'Customer *'),
                  isExpanded: true,
                  items: _customers
                      .map(
                        (customer) => DropdownMenuItem(
                          value: customer['code'].toString(),
                          child: Text(
                            '${customer['code']} — ${customer['name']}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: _changeCustomer,
                  validator: (value) =>
                      value == null ? 'Customer is required' : null,
                ),
              ),
              _box(
                _dateField(
                  'Delivery Date',
                  _deliveryDate,
                  (date) => _deliveryDate = date,
                ),
              ),
              _box(
                DropdownButtonFormField<String>(
                  initialValue: _orderType,
                  decoration: const InputDecoration(labelText: 'Order Type *'),
                  items: const [
                    DropdownMenuItem(
                      value: 'mass_pro',
                      child: Text('Mass Production'),
                    ),
                    DropdownMenuItem(
                      value: 'job_order',
                      child: Text('Job Order'),
                    ),
                    DropdownMenuItem(value: 'trial', child: Text('Trial')),
                  ],
                  onChanged: (value) => setState(() => _orderType = value!),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Text('Ship To', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          const Text(
            'Defaults to customer data. Change these fields for a different delivery destination.',
            style: TextStyle(color: Color(0xFF667085), fontSize: 13),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 16,
            runSpacing: 16,
            children: [
              _box(
                TextFormField(
                  controller: _shipToName,
                  decoration: const InputDecoration(
                    labelText: 'Recipient Name',
                  ),
                ),
              ),
              _box(
                TextFormField(
                  controller: _shipToContact,
                  decoration: const InputDecoration(
                    labelText: 'Contact Person',
                  ),
                ),
              ),
              _box(
                TextFormField(
                  controller: _shipToPhone,
                  decoration: const InputDecoration(labelText: 'Phone Number'),
                ),
              ),
              SizedBox(
                width: 586,
                child: TextFormField(
                  controller: _shipToAddress,
                  minLines: 2,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Ship To Address',
                  ),
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
                onPressed: _customerCode == null
                    ? null
                    : () => setState(() => _items.add(_SalesItemDraft())),
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
          const SizedBox(height: 16),
          TextFormField(
            controller: _notes,
            minLines: 3,
            maxLines: 5,
            decoration: const InputDecoration(labelText: 'Notes'),
          ),
        ],
      ),
    ),
  );

  SizedBox _box(Widget child) => SizedBox(width: 285, child: child);

  Widget _dateField(
    String label,
    DateTime value,
    ValueChanged<DateTime> onChanged,
  ) => InkWell(
    onTap: () async {
      final date = await _pickDate(value);
      if (date != null) setState(() => onChanged(date));
    },
    child: InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        suffixIcon: const Icon(Icons.calendar_today_outlined),
      ),
      child: Text(_date(value)),
    ),
  );

  Widget _itemCard(int index, _SalesItemDraft item) => Card(
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
                    : () => setState(() => _items.removeAt(index).dispose()),
                icon: const Icon(Icons.delete_outline),
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
                child: TextFormField(
                  controller: item.quantity,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(labelText: 'Quantity'),
                  validator: (value) => _number(value, 'Quantity'),
                ),
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
                child: TextFormField(
                  controller: item.price,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Unit Price (IDR)',
                  ),
                  validator: (value) =>
                      _number(value, 'Price', allowZero: true),
                ),
              ),
              SizedBox(
                width: 260,
                child: TextFormField(
                  controller: item.remark,
                  decoration: const InputDecoration(labelText: 'Remark'),
                ),
              ),
              SizedBox(
                width: 300,
                child: TextFormField(
                  controller: item.outstandingNote,
                  decoration: const InputDecoration(
                    labelText: 'Outstanding Note',
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class _SalesItemDraft {
  _SalesItemDraft({
    this.productCode,
    String quantity = '',
    String price = '',
    String remark = '',
    String outstandingNote = '',
    this.unit = 'pcs',
  }) : quantity = TextEditingController(text: quantity),
       price = TextEditingController(text: price),
       remark = TextEditingController(text: remark),
       outstandingNote = TextEditingController(text: outstandingNote);

  factory _SalesItemDraft.fromModel(SalesOrderItemModel item) =>
      _SalesItemDraft(
        productCode: item.productCode,
        quantity: item.quantityGrams.toString(),
        price: item.unitPrice.toString(),
        remark: item.remark,
        outstandingNote: item.outstandingNote,
        unit: item.unit,
      );

  String? productCode;
  String unit;
  final TextEditingController quantity;
  final TextEditingController price;
  final TextEditingController remark;
  final TextEditingController outstandingNote;

  void dispose() {
    quantity.dispose();
    price.dispose();
    remark.dispose();
    outstandingNote.dispose();
  }
}
