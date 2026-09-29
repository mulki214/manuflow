import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/mobile_product_scanner.dart';
import '../../shared/searchable_select_field.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';

class ReceivingFormDialog extends StatefulWidget {
  const ReceivingFormDialog({
    super.key,
    required this.auth,
    this.scannedItems = const [],
  });
  final AuthController auth;
  final List<ScannedProductIdentity> scannedItems;

  @override
  State<ReceivingFormDialog> createState() => _ReceivingFormDialogState();
}

class _ReceivingFormDialogState extends State<ReceivingFormDialog> {
  final _key = GlobalKey<FormState>();
  final _lot = TextEditingController();
  final _quantity = TextEditingController();
  final _document = TextEditingController();
  final _vehicle = TextEditingController();
  final _driver = TextEditingController();
  final _notes = TextEditingController();
  List<Map<String, dynamic>> _corporations = [];
  List<Map<String, dynamic>> _sourceItems = [];
  List<Map<String, dynamic>> _transportations = [];
  List<Map<String, dynamic>> _plants = [];
  List<Map<String, dynamic>> _locations = [];
  String _documentType = 'purchase_order';
  String _supplySource = 'external_supplier';
  String? _supplierCode;
  String? _customerCode;
  int? _sourceItemId;
  String? _transportationCode;
  String? _plantCode;
  String? _locationCode;
  String _transportSource = 'external';
  String _description = '-';
  String _documentNumber = '-';
  String _unit = '-';
  String _outstanding = '-';
  DateTime _receiptDate = DateTime.now();
  bool _loading = true;
  bool _saving = false;
  String? _error;

  List<Map<String, dynamic>> get _availableSourceItems => _sourceItems
      .where((item) => _hasOutstandingQuantity(item['outstanding_quantity']))
      .toList();

  List<Map<String, dynamic>> get _visibleSourceItems =>
      widget.scannedItems.isEmpty
      ? _availableSourceItems
      : _availableSourceItems
            .where(
              (item) => widget.scannedItems.any(
                (scan) => scan.productCode == item['product_code'],
              ),
            )
            .toList();

  bool _hasOutstandingQuantity(dynamic value) {
    final parsed = num.tryParse(value?.toString() ?? '');
    return parsed != null && parsed > 0;
  }

  void _applyScannedItemIfUnambiguous() {
    if (_sourceItemId != null || widget.scannedItems.length != 1) return;
    final scan = widget.scannedItems.single;
    final matches = _visibleSourceItems
        .where((item) => item['product_code'] == scan.productCode)
        .toList();
    if (matches.length != 1) return;
    _selectSourceItem(matches.single['item_id'] as int);
    if (scan.lotNumber != null && _lot.text.trim().isEmpty) {
      _lot.text = scan.lotNumber!;
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final controller in [
      _lot,
      _quantity,
      _document,
      _vehicle,
      _driver,
      _notes,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final responses = await Future.wait([
        widget.auth.api.getJson('/master-data/corporations?size=100'),
        widget.auth.api.getJson('/master-data/plants?size=100'),
        widget.auth.api.getJson(
          '/master-data/transportations?size=100&active_only=true',
        ),
      ]);
      _corporations = List<Map<String, dynamic>>.from(
        responses[0]['items'] as List,
      );
      _plants = List<Map<String, dynamic>>.from(responses[1]['items'] as List);
      _transportations = List<Map<String, dynamic>>.from(
        responses[2]['items'] as List,
      );
    } on ApiException catch (exception) {
      _error = exception.message;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _selectPlant(String? value) async {
    if (value == null) return;
    setState(() {
      _plantCode = value;
      _locationCode = null;
      _locations = [];
    });
    try {
      final response = await widget.auth.api.getJson(
        '/master-data/storage-locations?size=100&plant_code=${Uri.encodeQueryComponent(value)}',
      );
      if (mounted) {
        setState(
          () => _locations = List<Map<String, dynamic>>.from(
            response['items'] as List,
          ),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  Future<void> _selectDocumentType(String? value) async {
    if (value == null) return;
    setState(() {
      _documentType = value;
      _supplySource = 'external_supplier';
      _supplierCode = null;
      _customerCode = null;
      _sourceItemId = null;
      _sourceItems = [];
      _description = '-';
      _documentNumber = '-';
      _unit = '-';
      _outstanding = '-';
    });
  }

  void _resetSourceItem() {
    setState(() {
      _sourceItemId = null;
      _sourceItems = [];
      _description = '-';
      _documentNumber = '-';
      _unit = '-';
      _outstanding = '-';
    });
  }

  Future<void> _selectSupplier(String? value) async {
    _resetSourceItem();
    setState(() => _supplierCode = value);
    await _loadSourceItems();
  }

  Future<void> _selectCustomer(String? value) async {
    _resetSourceItem();
    setState(() => _customerCode = value);
    await _loadSourceItems();
  }

  Future<void> _selectSupplySource(String? value) async {
    if (value == null) return;
    _resetSourceItem();
    setState(() {
      _supplySource = value;
      if (value == 'manufactured_internally') _supplierCode = null;
    });
    await _loadSourceItems();
  }

  Future<void> _loadSourceItems() async {
    final supplier = _supplierCode;
    if (_supplySource == 'manufactured_internally') return;
    if (supplier == null ||
        (_documentType == 'sales_order' && _customerCode == null)) {
      return;
    }
    try {
      final sourceType = _documentType == 'sales_order'
          ? 'supplier'
          : 'customer';
      final response = await widget.auth.api.getJson(
        '/receiving/source-items?document_type=$_documentType&source_type=$sourceType&source_code=${Uri.encodeQueryComponent(supplier)}${_customerCode == null ? '' : '&customer_code=${Uri.encodeQueryComponent(_customerCode!)}'}',
      );
      if (mounted) {
        setState(() {
          _sourceItems = List<Map<String, dynamic>>.from(
            response['items'] as List? ?? const [],
          );
          if (_sourceItemId != null &&
              !_visibleSourceItems.any(
                (item) => item['item_id'] == _sourceItemId,
              )) {
            _sourceItemId = null;
            _description = '-';
            _documentNumber = '-';
            _unit = '-';
            _outstanding = '-';
          }
        });
        _applyScannedItemIfUnambiguous();
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  void _selectSourceItem(int? value) {
    if (value == null) return;
    final item = _sourceItems.firstWhere((entry) => entry['item_id'] == value);
    setState(() {
      _sourceItemId = value;
      _description = item['product_description'].toString();
      _documentNumber = item['document_number'].toString();
      _unit = item['unit'].toString();
      _outstanding =
          '${formatQuantity(item['outstanding_quantity'], _unit)} ${unitLabel(_unit)}';
    });
  }

  String _date(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  String? _optional(TextEditingController controller) =>
      controller.text.trim().isEmpty ? null : controller.text.trim();

  Future<void> _save() async {
    if (!_key.currentState!.validate()) return;
    if (_supplySource == 'manufactured_internally') {
      setState(
        () => _error =
            'Produk Manufactured Internally tidak diposting melalui Receiving. Lanjutkan melalui Production, QC, lalu Finish Good.',
      );
      return;
    }
    if (_supplierCode == null ||
        _sourceItemId == null ||
        _plantCode == null ||
        _locationCode == null) {
      setState(
        () => _error =
            'Supplier, Order Item, Plant, and Storage Location are required.',
      );
      return;
    }
    final quantity = double.parse(_quantity.text);
    if (isDiscreteUnit(_unit) && quantity != quantity.roundToDouble()) {
      setState(
        () =>
            _error = 'Quantity must be a whole number for ${unitLabel(_unit)}.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.auth.api.postJson('/receiving', {
        'receipt_date': _date(_receiptDate),
        'source_type': _documentType == 'sales_order' ? 'supplier' : 'customer',
        'source_code': _supplierCode,
        'source_document_item_id': _sourceItemId,
        'document_type': _documentType,
        'customer_code': _customerCode,
        'lot_number': _lot.text.trim(),
        'quantity_grams': quantity,
        'plant_code': _plantCode,
        'storage_location_code': _locationCode,
        'document_number': _optional(_document),
        'transport_source': _transportSource,
        'transportation_code': _transportationCode,
        'vehicle_number': _transportSource == 'external'
            ? _optional(_vehicle)
            : null,
        'driver_name': _transportSource == 'external'
            ? _optional(_driver)
            : null,
        'notes': _notes.text.trim(),
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Dialog(
    insetPadding: const EdgeInsets.all(16),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 850, maxHeight: 800),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 18, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Create Receiving',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
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
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.inventory_2_outlined),
                  label: const Text('Post Receiving'),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  Widget _form() => Form(
    key: _key,
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          const SizedBox(height: 12),
          if (widget.scannedItems.isNotEmpty) ...[
            Text(
              widget.scannedItems.length == 1
                  ? 'Scanned ${widget.scannedItems.single.productCode}${widget.scannedItems.single.lotNumber == null ? '' : ' · Lot ${widget.scannedItems.single.lotNumber}'}. Select the required source to validate and apply it.'
                  : '${widget.scannedItems.length} scanned products. Select the required source, then choose the matching item to receive.',
              style: const TextStyle(color: Color(0xFF475467)),
            ),
            const SizedBox(height: 12),
          ],
          Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [
              _box(_dateField()),
              _box(
                DropdownButtonFormField<String>(
                  initialValue: _documentType,
                  decoration: const InputDecoration(
                    labelText: 'Receiving Based On *',
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'purchase_order',
                      child: Text('Purchase Order (PO)'),
                    ),
                    DropdownMenuItem(
                      value: 'sales_order',
                      child: Text('Sales Order (SO)'),
                    ),
                  ],
                  onChanged: _selectDocumentType,
                ),
              ),
              _box(
                SearchableSelectField<String>(
                  value: _supplierCode,
                  labelText: 'Supplier *',
                  searchHint: 'Search supplier',
                  options: _corporations
                      .where((item) => item['is_supplier'] == true)
                      .map(
                        (item) => SearchableSelectOption(
                          value: item['code'].toString(),
                          label: '${item['code']} — ${item['name']}',
                          searchTerms: [
                            item['code'].toString(),
                            item['name']?.toString() ?? '',
                          ],
                        ),
                      )
                      .toList(),
                  onChanged: _supplySource == 'manufactured_internally'
                      ? null
                      : _selectSupplier,
                  validator: (value) =>
                      _supplySource == 'external_supplier' && value == null
                      ? 'Required'
                      : null,
                ),
              ),
              if (_documentType == 'sales_order') ...[
                _box(
                  SearchableSelectField<String>(
                    value: _customerCode,
                    labelText: 'Customer *',
                    searchHint: 'Search customer',
                    options: _corporations
                        .where((item) => item['is_customer'] == true)
                        .map(
                          (item) => SearchableSelectOption(
                            value: item['code'].toString(),
                            label: '${item['code']} — ${item['name']}',
                            searchTerms: [
                              item['code'].toString(),
                              item['name']?.toString() ?? '',
                            ],
                          ),
                        )
                        .toList(),
                    onChanged: _selectCustomer,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                ),
                _box(
                  DropdownButtonFormField<String>(
                    initialValue: _supplySource,
                    decoration: const InputDecoration(
                      labelText: 'Product Supply *',
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: 'external_supplier',
                        child: Text('External Supplier'),
                      ),
                      DropdownMenuItem(
                        value: 'manufactured_internally',
                        child: Text('Manufactured Internally'),
                      ),
                    ],
                    onChanged: _selectSupplySource,
                  ),
                ),
              ],
              if (_documentType == 'sales_order' &&
                  _supplySource == 'manufactured_internally')
                const SizedBox(
                  width: 584,
                  child: Text(
                    'Produk internal tidak diterima melalui Receiving. Jalankan Production, QC, lalu post Finish Good untuk memenuhi SO.',
                  ),
                ),
              SizedBox(
                width: 584,
                child: SearchableSelectField<int>(
                  value: _sourceItemId,
                  labelText: _documentType == 'sales_order'
                      ? 'Outstanding SO Receiving Item *'
                      : 'Outstanding PO Item *',
                  searchHint: 'Search order or product',
                  options: _visibleSourceItems
                      .map(
                        (item) => SearchableSelectOption(
                          value: item['item_id'] as int,
                          label:
                              '${item['document_number']} — ${item['product_description']} — ${formatQuantity(item['outstanding_quantity'], item['unit'].toString())} ${unitLabel(item['unit'].toString())}',
                          searchTerms: [
                            item['document_number']?.toString() ?? '',
                            item['product_code']?.toString() ?? '',
                            item['product_description']?.toString() ?? '',
                          ],
                        ),
                      )
                      .toList(),
                  onChanged: _supplySource == 'manufactured_internally'
                      ? null
                      : _selectSourceItem,
                  validator: (value) => value == null ? 'Required' : null,
                ),
              ),
              if (_supplierCode != null &&
                  _supplySource == 'external_supplier' &&
                  _visibleSourceItems.isEmpty)
                const SizedBox(
                  width: 584,
                  child: Text(
                    'No outstanding items are available for this source.',
                    style: TextStyle(color: Color(0xFF667085)),
                  ),
                ),
              SizedBox(
                width: 584,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Product Description',
                  ),
                  child: Text(_description),
                ),
              ),
              _box(_input(_lot, 'Lot Number *')),
              _box(_input(_quantity, 'Quantity *', number: true)),
              _box(
                InputDecorator(
                  decoration: const InputDecoration(labelText: 'Unit'),
                  child: Text(unitLabel(_unit)),
                ),
              ),
              _box(
                InputDecorator(
                  decoration: const InputDecoration(labelText: 'Outstanding'),
                  child: Text(_outstanding),
                ),
              ),
              _box(
                SearchableSelectField<String>(
                  value: _plantCode,
                  labelText: 'Plant *',
                  searchHint: 'Search plant',
                  options: _plants
                      .map(
                        (item) => SearchableSelectOption(
                          value: item['code'].toString(),
                          label: '${item['code']} — ${item['name']}',
                          searchTerms: [
                            item['code'].toString(),
                            item['name']?.toString() ?? '',
                          ],
                        ),
                      )
                      .toList(),
                  onChanged: _selectPlant,
                  validator: (value) => value == null ? 'Required' : null,
                ),
              ),
              _box(
                SearchableSelectField<String>(
                  value: _locationCode,
                  labelText: 'Storage Location *',
                  searchHint: 'Search storage location',
                  options: _locations
                      .map(
                        (item) => SearchableSelectOption(
                          value: item['code'].toString(),
                          label:
                              '${item['storage_name'] ?? 'Storage'} — ${item['name']}',
                          searchTerms: [
                            item['code'].toString(),
                            item['storage_name']?.toString() ?? '',
                            item['name']?.toString() ?? '',
                          ],
                        ),
                      )
                      .toList(),
                  onChanged: (value) => setState(() => _locationCode = value),
                  validator: (value) => value == null ? 'Required' : null,
                ),
              ),
              _box(_input(_document, 'Document Number', required: false)),
              _box(
                InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'PO / Customer Order',
                  ),
                  child: Text(_documentNumber),
                ),
              ),
              _box(
                DropdownButtonFormField<String>(
                  initialValue: _transportSource,
                  decoration: const InputDecoration(
                    labelText: 'Transport Source *',
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'external',
                      child: Text('External'),
                    ),
                    DropdownMenuItem(
                      value: 'internal',
                      child: Text('Internal'),
                    ),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() {
                      _transportSource = value;
                      _transportationCode = null;
                    });
                  },
                ),
              ),
              if (_transportSource == 'internal')
                _box(
                  SearchableSelectField<String>(
                    value: _transportationCode,
                    labelText: 'Internal Vehicle *',
                    searchHint: 'Search vehicle',
                    options: _transportations
                        .map(
                          (item) => SearchableSelectOption(
                            value: item['code'].toString(),
                            label: item['vehicle_number'].toString(),
                            searchTerms: [
                              item['code'].toString(),
                              item['vehicle_number']?.toString() ?? '',
                              item['carrier_name']?.toString() ?? '',
                            ],
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value == null) return;
                      setState(() {
                        _transportationCode = value;
                      });
                    },
                    validator: (value) =>
                        _transportSource == 'internal' && value == null
                        ? 'Required'
                        : null,
                  ),
                ),
              if (_transportSource == 'external') ...[
                _box(_input(_vehicle, 'Vehicle Number', required: false)),
                _box(_input(_driver, 'Driver Name', required: false)),
              ],
              _box(
                InputDecorator(
                  decoration: const InputDecoration(labelText: 'Receiver'),
                  child: Text(widget.auth.currentUser?.fullName ?? '-'),
                ),
              ),
              SizedBox(
                width: 584,
                child: _input(_notes, 'Notes', required: false, lines: 3),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  SizedBox _box(Widget child) => SizedBox(width: 285, child: child);

  Widget _input(
    TextEditingController controller,
    String label, {
    bool required = true,
    bool number = false,
    int lines = 1,
  }) => TextFormField(
    controller: controller,
    maxLines: lines,
    keyboardType: number
        ? TextInputType.numberWithOptions(decimal: !isDiscreteUnit(_unit))
        : TextInputType.text,
    decoration: InputDecoration(labelText: label),
    validator: (value) {
      if (required && (value == null || value.trim().isEmpty)) {
        return 'Required';
      }
      if (number &&
          (double.tryParse(value ?? '') == null || double.parse(value!) <= 0)) {
        return 'Must be greater than zero';
      }
      return null;
    },
  );

  Widget _dateField() => InkWell(
    onTap: () async {
      final date = await showDatePicker(
        context: context,
        initialDate: _receiptDate,
        firstDate: DateTime(2020),
        lastDate: DateTime(2200),
      );
      if (date != null) setState(() => _receiptDate = date);
    },
    child: InputDecorator(
      decoration: const InputDecoration(
        labelText: 'Receipt Date *',
        suffixIcon: Icon(Icons.calendar_today_outlined),
      ),
      child: Text(_date(_receiptDate)),
    ),
  );
}
