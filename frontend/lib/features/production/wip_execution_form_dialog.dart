import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';
import 'production_models.dart';

class WipExecutionFormDialog extends StatefulWidget {
  const WipExecutionFormDialog({
    super.key,
    required this.api,
    required this.job,
  });

  final ApiClient api;
  final ProductionWipJobModel job;

  @override
  State<WipExecutionFormDialog> createState() => _WipExecutionFormDialogState();
}

class _WipExecutionFormDialogState extends State<WipExecutionFormDialog> {
  final _key = GlobalKey<FormState>();
  final _processing = TextEditingController();
  final _good = TextEditingController();
  final _repair = TextEditingController(text: '0');
  final _ng = TextEditingController(text: '0');
  final _startTime = TextEditingController(text: '08:00');
  final _endTime = TextEditingController(text: '09:00');
  final _breakMinutes = TextEditingController(text: '0');
  final _observedCycle = TextEditingController();
  final _ngOverrideReason = TextEditingController();
  final _notes = TextEditingController();
  DateTime _date = DateTime.now();
  String _shift = 'Shift 1';
  String? _nextProcess;
  String? _repairProcess;
  String? _repairRoute;
  String? _machine;
  String? _outputProduct;
  String? _outputUnit;
  List<ProductionProcessModel> _processes = [];
  List<Map<String, dynamic>> _machines = [];
  List<Map<String, dynamic>> _products = [];
  List<Map<String, dynamic>> _repairRoutes = [];
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _processing.text = _number(widget.job.currentQuantity);
    _good.text = _number(widget.job.currentQuantity);
    _outputProduct = widget.job.productCode;
    _outputUnit = widget.job.unit;
    _load();
  }

  @override
  void dispose() {
    _processing.dispose();
    _good.dispose();
    _repair.dispose();
    _ng.dispose();
    _startTime.dispose();
    _endTime.dispose();
    _breakMinutes.dispose();
    _observedCycle.dispose();
    _ngOverrideReason.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final responses = await Future.wait([
        widget.api.getJson(
          '/production/processes?page=1&size=100&active_only=true&plant_code=${widget.job.plantCode}',
        ),
        widget.api.getJson('/master-data/machines?page=1&size=100'),
        widget.api.getJson('/master-data/products?page=1&size=100'),
        widget.api.getJson(
          '/production/repair-routes?product_code=${widget.job.productCode}',
        ),
      ]);
      if (!mounted) return;
      setState(() {
        _processes = (responses[0]['items'] as List)
            .map(
              (item) =>
                  ProductionProcessModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _machines = (responses[1]['items'] as List)
            .cast<Map<String, dynamic>>()
            .where((item) => item['plant_code'] == widget.job.plantCode)
            .toList();
        _products = (responses[2]['items'] as List)
            .cast<Map<String, dynamic>>()
            .toList();
        _repairRoutes = (responses[3] as List).cast<Map<String, dynamic>>();
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
    );
    if (selected != null) setState(() => _date = selected);
  }

  double _value(TextEditingController controller) =>
      double.tryParse(controller.text.trim()) ?? 0;

  Future<void> _save() async {
    if (!_key.currentState!.validate()) return;
    final processing = _value(_processing);
    final good = _value(_good);
    final repair = _value(_repair);
    final ng = _value(_ng);
    if ((good + repair + ng - processing).abs() > 0.0001) {
      setState(
        () => _error =
            'Good + Repair + NG Quantity must equal Processing Quantity.',
      );
      return;
    }
    if (processing > widget.job.currentQuantity) {
      setState(() => _error = 'Processing Quantity exceeds available WIP.');
      return;
    }
    if (repair > 0 && _repairProcess == null && _repairRoute == null) {
      setState(() => _error = 'Select a Repair Route or Repair Process.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api
          .postJson('/production/wip-jobs/${widget.job.id}/complete', {
            'process_date': _apiDate(_date),
            'shift': _shift,
            'started_at': _dateTime(_date, _startTime.text),
            'ended_at': _dateTime(_date, _endTime.text),
            'break_duration_minutes': int.tryParse(_breakMinutes.text) ?? 0,
            'observed_cycle_time_seconds': double.tryParse(_observedCycle.text),
            'ng_override_reason': _ngOverrideReason.text.trim().isEmpty
                ? null
                : _ngOverrideReason.text.trim(),
            'processing_quantity': processing,
            'good_quantity': good,
            'repair_quantity': repair,
            'ng_quantity': ng,
            'next_process_code': good > 0 ? _nextProcess : null,
            'repair_process_code': repair > 0 ? _repairProcess : null,
            'repair_route_code': repair > 0 ? _repairRoute : null,
            'output_product_code': good > 0 ? _outputProduct : null,
            'output_unit': good > 0 ? _outputUnit : null,
            'machine_code': _machine,
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
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 820, maxHeight: 820),
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _key,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Record WIP Production Result',
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                        IconButton(
                          onPressed: _saving
                              ? null
                              : () => Navigator.pop(context),
                          icon: const Icon(Icons.close),
                        ),
                      ],
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    Wrap(
                      spacing: 14,
                      runSpacing: 14,
                      children: [
                        _summary('Plant', widget.job.plantName),
                        _summary(
                          'Product',
                          '${widget.job.productCode} — ${widget.job.description}',
                        ),
                        _summary(
                          'Lot / Segment',
                          '${widget.job.lotNumber} / ${widget.job.segmentCode}',
                        ),
                        _summary(
                          'Before Process',
                          '${widget.job.processCode} — ${widget.job.processName}',
                        ),
                        _summary(
                          'Available WIP',
                          '${_number(widget.job.currentQuantity)} ${unitLabel(widget.job.unit)}',
                        ),
                        _summary(
                          'Warehouse Transfer',
                          widget.job.sourceTransferNumber,
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),
                    LayoutBuilder(
                      builder: (context, constraints) {
                        final wide = constraints.maxWidth >= 620;
                        final fields = [
                          InkWell(
                            onTap: _pickDate,
                            child: InputDecorator(
                              decoration: const InputDecoration(
                                labelText: 'Production Date *',
                              ),
                              child: Text(_displayDate(_date)),
                            ),
                          ),
                          DropdownButtonFormField<String>(
                            initialValue: _shift,
                            decoration: const InputDecoration(
                              labelText: 'Shift *',
                            ),
                            items: const [
                              DropdownMenuItem(
                                value: 'Shift 1',
                                child: Text('Shift 1'),
                              ),
                              DropdownMenuItem(
                                value: 'Shift 2',
                                child: Text('Shift 2'),
                              ),
                              DropdownMenuItem(
                                value: 'Shift 3',
                                child: Text('Shift 3'),
                              ),
                            ],
                            onChanged: (value) =>
                                setState(() => _shift = value ?? 'Shift 1'),
                          ),
                        ];
                        return wide
                            ? Row(
                                children: fields
                                    .map(
                                      (field) => Expanded(
                                        child: Padding(
                                          padding: const EdgeInsets.only(
                                            right: 10,
                                          ),
                                          child: field,
                                        ),
                                      ),
                                    )
                                    .toList(),
                              )
                            : Column(
                                children: fields
                                    .map(
                                      (field) => Padding(
                                        padding: const EdgeInsets.only(
                                          bottom: 12,
                                        ),
                                        child: field,
                                      ),
                                    )
                                    .toList(),
                              );
                      },
                    ),
                    const SizedBox(height: 14),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        _textField(
                          _startTime,
                          'Start Time (HH:mm) *',
                          width: 180,
                        ),
                        _textField(_endTime, 'End Time (HH:mm) *', width: 180),
                        _textField(
                          _breakMinutes,
                          'Break (minutes)',
                          width: 180,
                          number: true,
                        ),
                        _textField(
                          _observedCycle,
                          'Observed Cycle (seconds)',
                          width: 220,
                          number: true,
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _processing,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        labelText:
                            'Processing Quantity (${unitLabel(widget.job.unit)}) *',
                      ),
                      validator: (value) {
                        final parsed = double.tryParse(value ?? '');
                        if (parsed == null || parsed <= 0) {
                          return 'Enter a valid Quantity';
                        }
                        if (parsed > widget.job.currentQuantity) {
                          return 'Quantity exceeds available WIP';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 14),
                    Text(
                      'Outcome',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        _quantityField(
                          _good,
                          'Good Quantity',
                          unitLabel(widget.job.unit),
                        ),
                        _quantityField(
                          _repair,
                          'Repair Quantity',
                          widget.job.unit,
                        ),
                        _quantityField(
                          _ng,
                          'NG Quantity',
                          unitLabel(widget.job.unit),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _nextProcess,
                      decoration: const InputDecoration(
                        labelText: 'After Process for Good Output',
                      ),
                      isExpanded: true,
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text(
                            'Quality Queue (final Production process)',
                          ),
                        ),
                        ..._processes
                            .where(
                              (item) =>
                                  item.type == 'production' &&
                                  item.code != widget.job.processCode,
                            )
                            .map(
                              (item) => DropdownMenuItem(
                                value: item.code,
                                child: Text('${item.code} — ${item.name}'),
                              ),
                            ),
                      ],
                      onChanged: (value) =>
                          setState(() => _nextProcess = value),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _repairRoute,
                      decoration: const InputDecoration(
                        labelText: 'Repair Route',
                      ),
                      isExpanded: true,
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('Use a single Repair Process'),
                        ),
                        ..._repairRoutes.map(
                          (item) => DropdownMenuItem(
                            value: item['code'].toString(),
                            child: Text(
                              '${item['code']} — ${item['name']} (${(item['step_process_codes'] as List).join(' → ')})',
                            ),
                          ),
                        ),
                      ],
                      onChanged: (value) => setState(() {
                        _repairRoute = value;
                        if (value != null) _repairProcess = null;
                      }),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _repairProcess,
                      decoration: const InputDecoration(
                        labelText: 'Repair Process',
                      ),
                      isExpanded: true,
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('Select when Repair Quantity is entered'),
                        ),
                        ..._processes
                            .where((item) => item.type == 'repair')
                            .map(
                              (item) => DropdownMenuItem(
                                value: item.code,
                                child: Text('${item.code} — ${item.name}'),
                              ),
                            ),
                      ],
                      onChanged: _repairRoute != null
                          ? null
                          : (value) => setState(() => _repairProcess = value),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _machine,
                      decoration: const InputDecoration(labelText: 'Machine'),
                      isExpanded: true,
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Text('No Machine / Manual Process'),
                        ),
                        ..._machines.map(
                          (item) => DropdownMenuItem(
                            value: item['code'].toString(),
                            child: Text('${item['code']} — ${item['name']}'),
                          ),
                        ),
                      ],
                      onChanged: (value) => setState(() => _machine = value),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _outputProduct,
                      decoration: const InputDecoration(
                        labelText: 'Good Output Product',
                      ),
                      isExpanded: true,
                      items: _products
                          .map(
                            (item) => DropdownMenuItem(
                              value: item['code'].toString(),
                              child: Text(
                                '${item['code']} — ${item['description']}',
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) =>
                          setState(() => _outputProduct = value),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _outputUnit,
                      decoration: const InputDecoration(
                        labelText: 'Good Output Unit',
                      ),
                      items: inventoryUnits
                          .map(
                            (unit) => DropdownMenuItem(
                              value: unit,
                              child: Text(unitLabel(unit)),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _outputUnit = value),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _ngOverrideReason,
                      minLines: 2,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        labelText: 'Head NG Override Reason',
                        helperText:
                            'Required only when NG exceeds the configured maximum.',
                      ),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _notes,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(labelText: 'Notes'),
                    ),
                    const SizedBox(height: 20),
                    Align(
                      alignment: Alignment.centerRight,
                      child: Wrap(
                        spacing: 10,
                        children: [
                          TextButton(
                            onPressed: _saving
                                ? null
                                : () => Navigator.pop(context),
                            child: const Text('Cancel'),
                          ),
                          FilledButton.icon(
                            onPressed: _saving ? null : _save,
                            icon: const Icon(Icons.task_alt),
                            label: const Text('Complete Process'),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    ),
  );

  Widget _quantityField(
    TextEditingController controller,
    String label,
    String unit,
  ) => SizedBox(
    width: 220,
    child: TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(labelText: '$label ($unit) *'),
      validator: (value) {
        final parsed = double.tryParse(value ?? '');
        return parsed == null || parsed < 0 ? 'Enter zero or greater' : null;
      },
    ),
  );

  Widget _textField(
    TextEditingController controller,
    String label, {
    double width = 220,
    bool number = false,
  }) => SizedBox(
    width: width,
    child: TextFormField(
      controller: controller,
      keyboardType: number
          ? const TextInputType.numberWithOptions(decimal: true)
          : null,
      decoration: InputDecoration(labelText: label),
    ),
  );

  String? _dateTime(DateTime date, String time) {
    final parts = time.trim().split(':');
    if (parts.length != 2) return null;
    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    if (hour == null || minute == null || hour > 23 || minute > 59) return null;
    return DateTime(
      date.year,
      date.month,
      date.day,
      hour,
      minute,
    ).toIso8601String();
  }

  Widget _summary(String label, String value) => SizedBox(
    width: 230,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: Color(0xFF667085), fontSize: 12),
        ),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
    ),
  );
}

String _apiDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

String _displayDate(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';

String _number(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value
          .toStringAsFixed(3)
          .replaceFirst(RegExp(r'0+$'), '')
          .replaceFirst(RegExp(r'\.$'), '');
