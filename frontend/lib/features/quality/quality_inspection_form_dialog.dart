import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';
import '../production/production_models.dart';
import 'quality_models.dart';

class QualityInspectionFormDialog extends StatefulWidget {
  const QualityInspectionFormDialog({
    super.key,
    required this.api,
    required this.job,
  });
  final ApiClient api;
  final QualityWipJobModel job;
  @override
  State<QualityInspectionFormDialog> createState() =>
      _QualityInspectionFormDialogState();
}

class _QualityInspectionFormDialogState
    extends State<QualityInspectionFormDialog> {
  final _form = GlobalKey<FormState>();
  final _inspection = TextEditingController();
  final _pass = TextEditingController();
  final _repair = TextEditingController(text: '0');
  final _ng = TextEditingController(text: '0');
  final _problem = TextEditingController();
  final _notes = TextEditingController();
  final _ngOverrideReason = TextEditingController();
  DateTime _date = DateTime.now();
  String _shift = 'Shift 1';
  String? _repairProcess;
  String? _repairRoute;
  List<ProductionProcessModel> _processes = [];
  List<Map<String, dynamic>> _repairRoutes = [];
  bool _loading = true, _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _inspection.text = _n(widget.job.quantity);
    _pass.text = _n(widget.job.quantity);
    _load();
  }

  @override
  void dispose() {
    for (final c in [
      _inspection,
      _pass,
      _repair,
      _ng,
      _problem,
      _notes,
      _ngOverrideReason,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  String _n(double value) => value == value.roundToDouble()
      ? value.toInt().toString()
      : value.toString();
  double _v(TextEditingController c) => double.tryParse(c.text.trim()) ?? 0;
  String _apiDate(DateTime value) =>
      '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  Future<void> _load() async {
    try {
      final result = await widget.api.getJson(
        '/quality/repair-options?plant_code=${widget.job.plantCode}&product_code=${widget.job.productCode}',
      );
      if (mounted) {
        setState(() {
          _processes = (result['processes'] as List)
              .map(
                (item) => ProductionProcessModel.fromJson(
                  item as Map<String, dynamic>,
                ),
              )
              .toList();
          _repairRoutes = (result['routes'] as List)
              .cast<Map<String, dynamic>>();
        });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDate() async {
    final value = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2020),
      lastDate: DateTime(2200),
    );
    if (value != null) setState(() => _date = value);
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final inspection = _v(_inspection),
        pass = _v(_pass),
        repair = _v(_repair),
        ng = _v(_ng);
    if ((pass + repair + ng - inspection).abs() > .0001) {
      setState(
        () => _error =
            'Pass + Repair + NG Quantity must equal Inspection Quantity.',
      );
      return;
    }
    if (inspection > widget.job.quantity) {
      setState(
        () => _error =
            'Inspection Quantity exceeds available Quality Queue Quantity.',
      );
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
      await widget.api.postJson('/quality/wip-jobs/${widget.job.id}/inspect', {
        'inspection_date': _apiDate(_date),
        'shift': _shift,
        'inspection_quantity': inspection,
        'pass_quantity': pass,
        'repair_quantity': repair,
        'ng_quantity': ng,
        'repair_process_code': repair > 0 ? _repairProcess : null,
        'repair_route_code': repair > 0 ? _repairRoute : null,
        'ng_override_reason': _ngOverrideReason.text.trim().isEmpty
            ? null
            : _ngOverrideReason.text.trim(),
        'problem': _problem.text.trim(),
        'notes': _notes.text.trim(),
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
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
              key: _form,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Record Quality Inspection',
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
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    const SizedBox(height: 18),
                    Wrap(
                      spacing: 32,
                      runSpacing: 16,
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
                        _summary('Before Process', widget.job.beforeProcess),
                        _summary(
                          'Available Quality Queue',
                          '${_n(widget.job.quantity)} ${unitLabel(widget.job.unit)}',
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _pickDate,
                            icon: const Icon(Icons.calendar_today_outlined),
                            label: Text('Inspection Date: ${_apiDate(_date)}'),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: DropdownButtonFormField<String>(
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
                            onChanged: (v) => setState(() => _shift = v!),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _inspection,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        labelText:
                            'Inspection Quantity (${unitLabel(widget.job.unit)}) *',
                      ),
                      validator: (v) =>
                          _v(_inspection) <= 0 ? 'Required' : null,
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'Outcome',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 10),
                    LayoutBuilder(
                      builder: (context, c) {
                        final wide = c.maxWidth > 650;
                        final fields = [
                          _qty(
                            _pass,
                            'Pass to Finished Goods (${unitLabel(widget.job.unit)}) *',
                          ),
                          _qty(
                            _repair,
                            'Repair Quantity (${unitLabel(widget.job.unit)}) *',
                          ),
                          _qty(
                            _ng,
                            'NG Quantity (${unitLabel(widget.job.unit)}) *',
                          ),
                        ];
                        return wide
                            ? Row(
                                children: [
                                  for (var i = 0; i < fields.length; i++)
                                    Expanded(
                                      child: Padding(
                                        padding: EdgeInsets.only(
                                          right: i == fields.length - 1
                                              ? 0
                                              : 12,
                                        ),
                                        child: fields[i],
                                      ),
                                    ),
                                ],
                              )
                            : Column(children: fields);
                      },
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
                          : (v) => setState(() => _repairProcess = v),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _problem,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Problem / Defect',
                      ),
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
                    const SizedBox(height: 22),
                    Align(
                      alignment: Alignment.centerRight,
                      child: Wrap(
                        spacing: 12,
                        children: [
                          TextButton(
                            onPressed: _saving
                                ? null
                                : () => Navigator.pop(context),
                            child: const Text('Cancel'),
                          ),
                          FilledButton.icon(
                            onPressed: _saving ? null : _save,
                            icon: const Icon(Icons.fact_check_outlined),
                            label: Text(
                              _saving ? 'Saving...' : 'Record Inspection',
                            ),
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
  Widget _summary(String label, String value) => SizedBox(
    width: 220,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF667085))),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
      ],
    ),
  );
  Widget _qty(TextEditingController controller, String label) => TextFormField(
    controller: controller,
    keyboardType: const TextInputType.numberWithOptions(decimal: true),
    decoration: InputDecoration(labelText: label),
  );
}
