import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';

class ProductionSettingsDialog extends StatefulWidget {
  const ProductionSettingsDialog({super.key, required this.api});
  final ApiClient api;

  @override
  State<ProductionSettingsDialog> createState() =>
      _ProductionSettingsDialogState();
}

class _ProductionSettingsDialogState extends State<ProductionSettingsDialog>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  List<Map<String, dynamic>> _products = [];
  List<Map<String, dynamic>> _processes = [];
  List<Map<String, dynamic>> _machines = [];
  final _workingHours = TextEditingController();
  final _expectedOutput = TextEditingController();
  final _cycle = TextEditingController();
  final _maxNgQty = TextEditingController();
  final _maxNgPercent = TextEditingController();
  final _routeCode = TextEditingController();
  final _routeName = TextEditingController();
  String? _product;
  String? _process;
  String? _machine;
  String _unit = 'pcs';
  String? _routeProduct;
  String? _routeSource;
  String? _routeReturn;
  final List<String> _routeSteps = [];
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    for (final field in [
      _workingHours,
      _expectedOutput,
      _cycle,
      _maxNgQty,
      _maxNgPercent,
      _routeCode,
      _routeName,
    ]) {
      field.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.api.getJson('/master-data/products?page=1&size=100'),
        widget.api.getJson(
          '/production/processes?page=1&size=100&active_only=true',
        ),
        widget.api.getJson('/master-data/machines?page=1&size=100'),
      ]);
      if (!mounted) return;
      setState(() {
        _products = (values[0]['items'] as List).cast<Map<String, dynamic>>();
        _processes = (values[1]['items'] as List).cast<Map<String, dynamic>>();
        _machines = (values[2]['items'] as List).cast<Map<String, dynamic>>();
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  double? _number(TextEditingController value) =>
      double.tryParse(value.text.trim());

  Future<void> _saveStandard() async {
    if (_product == null ||
        _process == null ||
        _number(_workingHours) == null ||
        _number(_expectedOutput) == null) {
      setState(
        () => _error =
            'Product, Process, Working Hours, and Expected Output are required.',
      );
      return;
    }
    await _submit('/production/standards', {
      'product_code': _product,
      'process_code': _process,
      'machine_code': _machine,
      'working_hours': _number(_workingHours),
      'expected_output_quantity': _number(_expectedOutput),
      'output_unit': _unit,
      'target_cycle_time_seconds': _number(_cycle),
      'maximum_ng_quantity': _number(_maxNgQty),
      'maximum_ng_percent': _number(_maxNgPercent),
      'is_active': true,
    });
  }

  Future<void> _saveRoute() async {
    if (_routeCode.text.trim().isEmpty ||
        _routeName.text.trim().isEmpty ||
        _routeProduct == null ||
        _routeSource == null ||
        _routeSteps.isEmpty) {
      setState(
        () => _error =
            'Code, Name, Product, Source Process, and at least one Repair step are required.',
      );
      return;
    }
    await _submit('/production/repair-routes', {
      'code': _routeCode.text.trim(),
      'name': _routeName.text.trim(),
      'product_code': _routeProduct,
      'source_process_code': _routeSource,
      'return_process_code': _routeReturn,
      'step_process_codes': _routeSteps,
      'is_active': true,
    });
  }

  Future<void> _submit(String path, Map<String, dynamic> body) async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.postJson(path, body);
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Dialog(
    child: SizedBox(
      width: 820,
      height: 720,
      child: Column(
        children: [
          ListTile(
            title: const Text(
              'Production Controls',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            trailing: IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
          ),
          TabBar(
            controller: _tabs,
            tabs: const [
              Tab(text: 'Product Standard'),
              Tab(text: 'Repair Route'),
            ],
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(10),
              child: Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : TabBarView(
                    controller: _tabs,
                    children: [_standardForm(), _routeForm()],
                  ),
          ),
        ],
      ),
    ),
  );

  Widget _standardForm() => _form([
    _dropdown(
      'Product',
      _product,
      _products,
      (value) => setState(() => _product = value),
    ),
    _dropdown(
      'Process',
      _process,
      _processes.where((item) => item['process_type'] == 'production').toList(),
      (value) => setState(() => _process = value),
    ),
    _dropdown(
      'Machine (optional)',
      _machine,
      _machines,
      (value) => setState(() => _machine = value),
      optional: true,
    ),
    _field(_workingHours, 'Working Hours'),
    _field(_expectedOutput, 'Expected Product Output'),
    DropdownButtonFormField<String>(
      initialValue: _unit,
      decoration: const InputDecoration(labelText: 'Output Unit'),
      items: inventoryUnits
          .map(
            (value) =>
                DropdownMenuItem(value: value, child: Text(unitLabel(value))),
          )
          .toList(),
      onChanged: (value) => setState(() => _unit = value ?? 'pcs'),
    ),
    _field(_cycle, 'Target Cycle Time (seconds)', optional: true),
    _field(_maxNgQty, 'Maximum NG Quantity', optional: true),
    _field(_maxNgPercent, 'Maximum NG Percent', optional: true),
  ], _saveStandard);

  Widget _routeForm() => _form([
    _field(_routeCode, 'Route Code', numeric: false),
    _field(_routeName, 'Route Name', numeric: false),
    _dropdown(
      'Product',
      _routeProduct,
      _products,
      (value) => setState(() => _routeProduct = value),
    ),
    _dropdown(
      'Source Process',
      _routeSource,
      _processes.where((item) => item['process_type'] == 'production').toList(),
      (value) => setState(() => _routeSource = value),
    ),
    _dropdown(
      'Return Process (blank = Quality)',
      _routeReturn,
      _processes.where((item) => item['process_type'] == 'production').toList(),
      (value) => setState(() => _routeReturn = value),
      optional: true,
    ),
    const Text(
      'Ordered Repair Steps',
      style: TextStyle(fontWeight: FontWeight.w700),
    ),
    Wrap(
      spacing: 8,
      children: _processes
          .where((item) => item['process_type'] == 'repair')
          .map(
            (item) => FilterChip(
              label: Text('${item['code']} — ${item['name']}'),
              selected: _routeSteps.contains(item['code']),
              onSelected: (selected) => setState(() {
                final code = item['code'].toString();
                selected ? _routeSteps.add(code) : _routeSteps.remove(code);
              }),
            ),
          )
          .toList(),
    ),
    if (_routeSteps.isNotEmpty) Text('Sequence: ${_routeSteps.join(' → ')}'),
  ], _saveRoute);

  Widget _form(List<Widget> fields, VoidCallback save) => SingleChildScrollView(
    padding: const EdgeInsets.all(22),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final field in fields) ...[field, const SizedBox(height: 12)],
        FilledButton(
          onPressed: _saving ? null : save,
          child: Text(_saving ? 'Saving...' : 'Save'),
        ),
      ],
    ),
  );

  Widget _field(
    TextEditingController controller,
    String label, {
    bool optional = false,
    bool numeric = true,
  }) => TextField(
    controller: controller,
    keyboardType: numeric
        ? const TextInputType.numberWithOptions(decimal: true)
        : null,
    decoration: InputDecoration(labelText: '$label${optional ? '' : ' *'}'),
  );

  Widget _dropdown(
    String label,
    String? value,
    List<Map<String, dynamic>> items,
    ValueChanged<String?> changed, {
    bool optional = false,
  }) => DropdownButtonFormField<String>(
    initialValue: value,
    isExpanded: true,
    decoration: InputDecoration(labelText: '$label${optional ? '' : ' *'}'),
    items: [
      if (optional) const DropdownMenuItem(value: null, child: Text('None')),
      ...items.map(
        (item) => DropdownMenuItem(
          value: item['code'].toString(),
          child: Text(
            '${item['code']} — ${item['name'] ?? item['part_name']}',
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ),
    ],
    onChanged: changed,
  );
}
