import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import 'master_data_models.dart';

class MasterDataFormDialog extends StatefulWidget {
  const MasterDataFormDialog({
    super.key,
    required this.api,
    required this.type,
    this.record,
  });

  final ApiClient api;
  final MasterDataType type;
  final MasterDataRecord? record;

  @override
  State<MasterDataFormDialog> createState() => _MasterDataFormDialogState();
}

class _MasterDataFormDialogState extends State<MasterDataFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _fields = {};
  List<LookupOption> _customers = [];
  List<LookupOption> _suppliers = [];
  List<LookupOption> _plants = [];
  List<LookupOption> _storages = [];
  List<LookupOption> _users = [];
  String? _customerCode;
  String? _supplierCode;
  String? _plantCode;
  final Set<String> _picUserIds = {};
  String? _headUserId;
  String? _storageCode;
  String _storageType = 'general';
  String _productCategory = 'finished_good';
  String _productSupplySource = 'external_supplier';
  bool _transportationActive = true;
  bool _isCustomer = false;
  bool _isSupplier = false;
  bool _saving = false;
  bool _loadingLookups = false;
  bool _descriptionTouched = false;
  bool _settingDescription = false;
  String? _error;

  bool get _editing => widget.record != null;

  TextEditingController field(String name) =>
      _fields.putIfAbsent(name, () => TextEditingController());

  @override
  void initState() {
    super.initState();
    final data = widget.record?.data ?? const <String, dynamic>{};
    for (final entry in data.entries) {
      if (entry.value is String || entry.value is num) {
        field(entry.key).text = entry.value.toString();
      }
    }
    _isCustomer = data['is_customer'] == true;
    _isSupplier = data['is_supplier'] == true;
    _customerCode = data['customer_code']?.toString();
    _supplierCode = data['supplier_code']?.toString();
    _plantCode = data['plant_code']?.toString();
    _picUserIds.addAll(
      (data['pic_user_ids'] as List? ?? const []).map(
        (value) => value.toString(),
      ),
    );
    _headUserId = data['head_user_id']?.toString();
    _storageCode = data['storage_code']?.toString();
    _storageType = data['storage_type']?.toString() ?? 'general';
    _productCategory = data['category']?.toString() ?? 'finished_good';
    _productSupplySource =
        data['supply_source']?.toString() ?? 'external_supplier';
    _transportationActive = data['is_active'] != false;
    if (widget.type == MasterDataType.product) {
      _descriptionTouched = _editing;
      field('description').addListener(() {
        if (!_settingDescription) _descriptionTouched = true;
      });
      field('part_name').addListener(_updateDefaultDescription);
      field('part_no').addListener(_updateDefaultDescription);
    }
    if (widget.type == MasterDataType.department ||
        widget.type == MasterDataType.product ||
        widget.type == MasterDataType.machine ||
        widget.type == MasterDataType.warehouseStorage ||
        widget.type == MasterDataType.storageLocation) {
      _loadLookups();
    }
  }

  Future<void> _loadLookups() async {
    setState(() => _loadingLookups = true);
    try {
      if (widget.type == MasterDataType.department) {
        final response = await widget.api.getJson('/users?size=100');
        _users = (response['items'] as List)
            .map(
              (item) => LookupOption(
                code: item['id'] as String,
                name: '${item['first_name']} ${item['last_name']}'.trim(),
              ),
            )
            .toList();
      } else if (widget.type == MasterDataType.product) {
        final customerResponse = await widget.api.getJson(
          '/master-data/corporations?customer_only=true&size=100',
        );
        final supplierResponse = await widget.api.getJson(
          '/master-data/corporations?supplier_only=true&size=100',
        );
        _customers = (customerResponse['items'] as List)
            .map(
              (item) => LookupOption(
                code: item['code'] as String,
                name: item['name'] as String,
              ),
            )
            .toList();
        _suppliers = (supplierResponse['items'] as List)
            .map(
              (item) => LookupOption(
                code: item['code'] as String,
                name: item['name'] as String,
              ),
            )
            .toList();
      } else {
        final response = await widget.api.getJson(
          '/master-data/plants?size=100',
        );
        _plants = (response['items'] as List)
            .map(
              (item) => LookupOption(
                code: item['code'] as String,
                name: item['name'] as String,
              ),
            )
            .toList();
        if (widget.type == MasterDataType.storageLocation) {
          final storageResponse = await widget.api.getJson(
            '/master-data/warehouse-storages?size=100',
          );
          _storages = (storageResponse['items'] as List)
              .map(
                (item) => LookupOption(
                  code: item['code'] as String,
                  name: '${item['name']} — ${item['plant_name']}',
                ),
              )
              .toList();
        }
      }
    } on ApiException catch (exception) {
      _error = exception.message;
    } finally {
      if (mounted) setState(() => _loadingLookups = false);
    }
  }

  void _updateDefaultDescription() {
    if (_descriptionTouched) return;
    _settingDescription = true;
    field(
      'description',
    ).text = '${field('part_name').text.trim()} ${field('part_no').text.trim()}'
        .trim();
    _settingDescription = false;
  }

  @override
  void dispose() {
    for (final controller in _fields.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    if (widget.type == MasterDataType.corporation &&
        !_isCustomer &&
        !_isSupplier) {
      setState(
        () => _error = 'Corporation must be a customer, supplier, or both.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final body = _buildBody();
    final basePath = '/master-data/${widget.type.endpoint}';
    try {
      if (_editing) {
        await widget.api.patchJson('$basePath/${widget.record!.code}', body);
      } else {
        await widget.api.postJson(basePath, body);
      }
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to connect to the server.');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Map<String, dynamic> _buildBody() => switch (widget.type) {
    MasterDataType.department => {
      'name': field('name').text.trim(),
      'pic_user_ids': _picUserIds.toList(),
      'head_user_id': _headUserId,
    },
    MasterDataType.corporation => {
      'name': field('name').text.trim(),
      'address': field('address').text.trim(),
      'phone_number': field('phone_number').text.trim(),
      'contact_person_name': field('contact_person_name').text.trim(),
      'contact_person_phone': field('contact_person_phone').text.trim(),
      'npwp': field('npwp').text.trim(),
      'is_customer': _isCustomer,
      'is_supplier': _isSupplier,
    },
    MasterDataType.plant => {
      'name': field('name').text.trim(),
      'full_address': field('full_address').text.trim(),
    },
    MasterDataType.product => {
      'customer_code': _customerCode,
      'supplier_code': _supplierCode,
      'supply_source': _productSupplySource,
      'part_name': field('part_name').text.trim(),
      'part_no': field('part_no').text.trim(),
      'description': field('description').text.trim(),
      'gross_weight': double.tryParse(field('gross_weight').text),
      'nett_weight': double.tryParse(field('nett_weight').text),
      'category': _productCategory,
    },
    MasterDataType.machine => {
      'name': field('name').text.trim(),
      'specification': field('specification').text.trim(),
      'machine_type': field('machine_type').text.trim(),
      'year': int.tryParse(field('year').text),
      'country_of_origin': field('country_of_origin').text.trim(),
      'plant_code': _plantCode,
    },
    MasterDataType.warehouseStorage => {
      'name': field('name').text.trim(),
      'storage_type': _storageType,
      'plant_code': _plantCode,
      'description': field('description').text.trim(),
    },
    MasterDataType.transportation => {
      'vehicle_number': field('vehicle_number').text.trim(),
      'vehicle_type': field('vehicle_type').text.trim(),
      'brand_name': field('brand_name').text.trim().isEmpty
          ? null
          : field('brand_name').text.trim(),
      'manufacturing_year': int.tryParse(field('manufacturing_year').text),
      'carrier_name': field('carrier_name').text.trim(),
      'capacity': double.tryParse(field('capacity').text),
      'notes': field('notes').text.trim(),
      'is_active': _transportationActive,
    },
    MasterDataType.storageLocation => {
      'name': field('name').text.trim(),
      'plant_code': _plantCode,
      'storage_code': _storageCode,
      'description': field('description').text.trim(),
    },
  };

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final dialogWidth = width >= 760 ? 720.0 : width - 32;
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: dialogWidth, maxHeight: 820),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${_editing ? 'Update' : 'Create'} ${widget.type.label}',
                        style: const TextStyle(
                          fontSize: 22,
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
                const SizedBox(height: 6),
                Text(
                  _editing
                      ? 'The generated code cannot be changed.'
                      : 'The code will be generated automatically.',
                  style: const TextStyle(color: Color(0xFF667085)),
                ),
                const SizedBox(height: 24),
                if (_loadingLookups)
                  const LinearProgressIndicator()
                else
                  _formFields(),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: _saving ? null : () => Navigator.pop(context),
                      child: const Text('Cancel'),
                    ),
                    const SizedBox(width: 10),
                    FilledButton(
                      onPressed: _saving || _loadingLookups ? null : _save,
                      child: _saving
                          ? const SizedBox.square(
                              dimension: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Text(_editing ? 'Save Changes' : 'Create'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _formFields() {
    final children = switch (widget.type) {
      MasterDataType.department => <Widget>[
        input('name', 'Department Name'),
        _multiPicSelector(),
        lookup(
          label: 'Head Name',
          options: _users,
          value: _headUserId,
          onChanged: (value) => setState(() => _headUserId = value),
        ),
      ],
      MasterDataType.corporation => <Widget>[
        input('name', 'Company Name'),
        input('phone_number', 'Company Phone', phone: true),
        input('contact_person_name', 'Contact Person Name'),
        input('contact_person_phone', 'Contact Person Phone', phone: true),
        input('npwp', 'NPWP'),
        input('address', 'Full Address', lines: 3),
        CheckboxListTile(
          value: _isCustomer,
          contentPadding: EdgeInsets.zero,
          title: const Text('Customer'),
          onChanged: (value) => setState(() => _isCustomer = value ?? false),
        ),
        CheckboxListTile(
          value: _isSupplier,
          contentPadding: EdgeInsets.zero,
          title: const Text('Supplier'),
          onChanged: (value) => setState(() => _isSupplier = value ?? false),
        ),
      ],
      MasterDataType.product => <Widget>[
        DropdownButtonFormField<String>(
          initialValue: _productCategory,
          decoration: const InputDecoration(labelText: 'Product Category'),
          items:
              const {
                    'raw_material': 'Raw Material',
                    'work_in_progress': 'Work In Progress',
                    'finished_good': 'Finished Good',
                  }.entries
                  .map(
                    (entry) => DropdownMenuItem(
                      value: entry.key,
                      child: Text(entry.value),
                    ),
                  )
                  .toList(),
          onChanged: (value) =>
              setState(() => _productCategory = value ?? 'finished_good'),
        ),
        DropdownButtonFormField<String>(
          initialValue: _productSupplySource,
          decoration: const InputDecoration(labelText: 'Product Supply'),
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
          onChanged: (value) => setState(() {
            _productSupplySource = value ?? 'external_supplier';
            if (_productSupplySource == 'manufactured_internally') {
              _supplierCode = null;
            }
          }),
        ),
        DropdownButtonFormField<String>(
          initialValue: _customers.any((item) => item.code == _customerCode)
              ? _customerCode
              : null,
          decoration: const InputDecoration(labelText: 'Customer Code'),
          items: _customers
              .map(
                (item) => DropdownMenuItem(
                  value: item.code,
                  child: Text(item.label, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: (value) => setState(() => _customerCode = value),
          validator: (value) => value == null ? 'Required' : null,
        ),
        if (_productSupplySource == 'external_supplier')
          DropdownButtonFormField<String>(
            initialValue: _suppliers.any((item) => item.code == _supplierCode)
                ? _supplierCode
                : null,
            decoration: const InputDecoration(labelText: 'Supplier Code *'),
            items: _suppliers
                .map(
                  (item) => DropdownMenuItem(
                    value: item.code,
                    child: Text(item.label, overflow: TextOverflow.ellipsis),
                  ),
                )
                .toList(),
            onChanged: (value) => setState(() => _supplierCode = value),
            validator: (value) => value == null ? 'Required' : null,
          ),
        if (_productSupplySource == 'manufactured_internally')
          const Text(
            'Produk ini masuk stok melalui Production → QC → Finish Good, bukan Receiving.',
          ),
        input('part_name', 'Part Name'),
        input('part_no', 'Part No'),
        input('gross_weight', 'Gross Weight (g)', number: true),
        input('nett_weight', 'Nett Weight (g)', number: true),
        input('description', 'Description', lines: 3),
      ],
      MasterDataType.machine => <Widget>[
        input('name', 'Machine Name'),
        input('machine_type', 'Machine Type'),
        input('year', 'Machine Year', integer: true),
        input('country_of_origin', 'Country of Origin'),
        DropdownButtonFormField<String>(
          initialValue: _plants.any((item) => item.code == _plantCode)
              ? _plantCode
              : null,
          decoration: const InputDecoration(labelText: 'Plant Location'),
          items: _plants
              .map(
                (item) => DropdownMenuItem(
                  value: item.code,
                  child: Text(item.label, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: (value) => setState(() => _plantCode = value),
          validator: (value) => value == null ? 'Required' : null,
        ),
        input('specification', 'Machine Specification', lines: 4),
      ],
      MasterDataType.plant => <Widget>[
        input('name', 'Plant Name'),
        input('full_address', 'Plant Full Address', lines: 4),
      ],
      MasterDataType.warehouseStorage => <Widget>[
        input('name', 'Storage Name'),
        DropdownButtonFormField<String>(
          initialValue: _storageType,
          decoration: const InputDecoration(labelText: 'Storage Type'),
          items:
              const {
                    'raw_material': 'Raw Material',
                    'work_in_progress': 'Work In Progress',
                    'finished_goods': 'Finished Goods',
                    'general': 'General',
                  }.entries
                  .map(
                    (entry) => DropdownMenuItem(
                      value: entry.key,
                      child: Text(entry.value),
                    ),
                  )
                  .toList(),
          onChanged: (value) =>
              setState(() => _storageType = value ?? 'general'),
        ),
        lookup(
          label: 'Plant',
          options: _plants,
          value: _plantCode,
          onChanged: (value) => setState(() => _plantCode = value),
        ),
        input('description', 'Description', lines: 3),
      ],
      MasterDataType.transportation => <Widget>[
        input('vehicle_number', 'Vehicle Number'),
        DropdownButtonFormField<String>(
          initialValue:
              const [
                'Truck',
                'Pickup',
                'Van',
                'Motorcycle',
                'Other',
              ].contains(field('vehicle_type').text)
              ? field('vehicle_type').text
              : null,
          decoration: const InputDecoration(labelText: 'Vehicle Type'),
          items: const ['Truck', 'Pickup', 'Van', 'Motorcycle', 'Other']
              .map(
                (value) => DropdownMenuItem(value: value, child: Text(value)),
              )
              .toList(),
          onChanged: (value) => field('vehicle_type').text = value ?? '',
          validator: (value) => value == null ? 'Required' : null,
        ),
        input('brand_name', 'Brand Name'),
        input('manufacturing_year', 'Manufacturing Year', integer: true),
        input('carrier_name', 'Carrier / Owner'),
        input('capacity', 'Capacity (kg)', number: true),
        input('notes', 'Notes', lines: 3),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Active'),
          value: _transportationActive,
          onChanged: (value) => setState(() => _transportationActive = value),
        ),
      ],
      MasterDataType.storageLocation => <Widget>[
        input('name', 'Storage Location Name'),
        DropdownButtonFormField<String>(
          initialValue: _plants.any((item) => item.code == _plantCode)
              ? _plantCode
              : null,
          decoration: const InputDecoration(labelText: 'Plant'),
          items: _plants
              .map(
                (item) => DropdownMenuItem(
                  value: item.code,
                  child: Text(item.label, overflow: TextOverflow.ellipsis),
                ),
              )
              .toList(),
          onChanged: (value) => setState(() => _plantCode = value),
          validator: (value) => value == null ? 'Required' : null,
        ),
        lookup(
          label: 'Storage / Warehouse',
          options: _storages,
          value: _storageCode,
          onChanged: (value) => setState(() => _storageCode = value),
        ),
        input('description', 'Description', lines: 3),
      ],
    };
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 620;
        return Wrap(
          spacing: 14,
          runSpacing: 14,
          children: children
              .map(
                (child) => SizedBox(
                  width: wide
                      ? (constraints.maxWidth - 14) / 2
                      : constraints.maxWidth,
                  child: child,
                ),
              )
              .toList(),
        );
      },
    );
  }

  Widget _multiPicSelector() => FormField<Set<String>>(
    initialValue: _picUserIds,
    validator: (_) => _picUserIds.isEmpty ? 'Select at least one PIC' : null,
    builder: (state) => InputDecorator(
      decoration: InputDecoration(
        labelText: 'PIC Names',
        errorText: state.errorText,
        border: const OutlineInputBorder(),
      ),
      child: Wrap(
        spacing: 8,
        runSpacing: 4,
        children: _users
            .map(
              (user) => FilterChip(
                label: Text(user.name),
                selected: _picUserIds.contains(user.code),
                onSelected: (selected) {
                  setState(() {
                    if (selected) {
                      _picUserIds.add(user.code);
                    } else {
                      _picUserIds.remove(user.code);
                    }
                    state.didChange(_picUserIds);
                  });
                },
              ),
            )
            .toList(),
      ),
    ),
  );

  Widget input(
    String key,
    String label, {
    int lines = 1,
    bool phone = false,
    bool number = false,
    bool integer = false,
  }) {
    return TextFormField(
      controller: field(key),
      maxLines: lines,
      keyboardType: phone
          ? TextInputType.phone
          : number || integer
          ? const TextInputType.numberWithOptions(decimal: true)
          : TextInputType.text,
      decoration: InputDecoration(labelText: label),
      validator: (value) {
        if (value == null || value.trim().isEmpty) return 'Required';
        if (number &&
            (double.tryParse(value) == null || double.parse(value) < 0)) {
          return 'Enter a valid non-negative number';
        }
        if (integer && int.tryParse(value) == null) return 'Enter a valid year';
        return null;
      },
    );
  }

  Widget lookup({
    required String label,
    required List<LookupOption> options,
    required String? value,
    required ValueChanged<String?> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      initialValue: options.any((item) => item.code == value) ? value : null,
      decoration: InputDecoration(labelText: label),
      items: options
          .map(
            (item) => DropdownMenuItem(
              value: item.code,
              child: Text(item.label, overflow: TextOverflow.ellipsis),
            ),
          )
          .toList(),
      onChanged: onChanged,
      validator: (selected) => selected == null ? 'Required' : null,
    );
  }
}
