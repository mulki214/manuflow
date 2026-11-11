import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api_client.dart';
import '../../shared/searchable_select_field.dart';
import '../../shared/units.dart';
import 'production_models.dart';

class InterPlantWipTransferDialog extends StatefulWidget {
  const InterPlantWipTransferDialog({
    super.key,
    required this.api,
    required this.job,
  });

  final ApiClient api;
  final ProductionWipJobModel job;

  @override
  State<InterPlantWipTransferDialog> createState() =>
      _InterPlantWipTransferDialogState();
}

class _InterPlantWipTransferDialogState
    extends State<InterPlantWipTransferDialog> {
  final _formKey = GlobalKey<FormState>();
  final _quantity = TextEditingController();
  final _notes = TextEditingController();
  List<ProductionProcessModel> _destinations = [];
  String? _destinationProcessCode;
  DateTime _date = DateTime.now();
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _quantity.text = _format(widget.job.currentQuantity);
    _loadDestinations();
  }

  @override
  void dispose() {
    _quantity.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _loadDestinations() async {
    try {
      final response = await widget.api.getJson(
        '/production/wip-jobs/${widget.job.id}/inter-plant-destinations',
      );
      if (!mounted) return;
      setState(() {
        _destinations = (response as List)
            .map(
              (item) =>
                  ProductionProcessModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
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

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate() || _destinationProcessCode == null) {
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.postJson(
        '/production/wip-jobs/${widget.job.id}/inter-plant-transfers',
        {
          'transfer_date': _apiDate(_date),
          'destination_process_code': _destinationProcessCode,
          'quantity': double.parse(_quantity.text),
          'notes': _notes.text.trim(),
        },
      );
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    return Dialog(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: 680,
          maxHeight: size.height * 0.9,
        ),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Transfer WIP to Another Plant',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                '${widget.job.productCode} — ${widget.job.description}\n'
                'Lot ${widget.job.lotNumber} • ${widget.job.processCode} — ${widget.job.processName}\n'
                'Source: ${widget.job.plantCode} — ${widget.job.plantName} • '
                'Available: ${_format(widget.job.currentQuantity)} ${unitLabel(widget.job.unit)}',
              ),
              const SizedBox(height: 16),
              if (_loading)
                const Expanded(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_destinations.isEmpty)
                const Expanded(
                  child: Center(
                    child: Text(
                      'No destination OP is configured for this product. '
                      'Add an active Product Process Standard at another plant first.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                Flexible(
                  child: Form(
                    key: _formKey,
                    child: ListView(
                      shrinkWrap: true,
                      children: [
                        OutlinedButton.icon(
                          onPressed: _saving ? null : _pickDate,
                          icon: const Icon(Icons.calendar_today_outlined),
                          label: Text('Transfer Date • ${_apiDate(_date)}'),
                        ),
                        const SizedBox(height: 12),
                        SearchableSelectField<String>(
                          value: _destinationProcessCode,
                          labelText: 'Destination Plant / OP *',
                          searchHint: 'Search plant or process',
                          options: _destinations
                              .map(
                                (process) => SearchableSelectOption<String>(
                                  value: process.code,
                                  label:
                                      '${process.plantCode} — ${process.plantName} • ${process.code} — ${process.name}',
                                  searchTerms: [
                                    process.plantCode,
                                    process.plantName,
                                    process.code,
                                    process.name,
                                  ],
                                ),
                              )
                              .toList(),
                          validator: (value) => value == null
                              ? 'Destination Plant / OP is required'
                              : null,
                          onChanged: (value) =>
                              setState(() => _destinationProcessCode = value),
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _quantity,
                          enabled: !_saving,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          inputFormatters: [
                            FilteringTextInputFormatter.allow(
                              RegExp(r'^\d*\.?\d{0,3}'),
                            ),
                          ],
                          decoration: InputDecoration(
                            labelText:
                                'Quantity (${unitLabel(widget.job.unit)}) *',
                            helperText:
                                'Must not exceed available WIP; discrete units must be whole numbers.',
                          ),
                          validator: (value) {
                            final quantity = double.tryParse(value ?? '');
                            if (quantity == null || quantity <= 0) {
                              return 'Enter a quantity greater than zero';
                            }
                            if (quantity > widget.job.currentQuantity) {
                              return 'Quantity exceeds available WIP';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _notes,
                          enabled: !_saving,
                          maxLines: 3,
                          decoration: const InputDecoration(labelText: 'Notes'),
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
                        const SizedBox(height: 16),
                        const Text(
                          'Dispatch reduces the source WIP immediately. The destination OP receives the quantity only after the receiving plant confirms receipt.',
                        ),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving ? null : () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.icon(
                    onPressed: _saving || _loading || _destinations.isEmpty
                        ? null
                        : _submit,
                    icon: _saving
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.local_shipping_outlined),
                    label: const Text('Dispatch WIP'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _apiDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

String _format(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value
          .toStringAsFixed(3)
          .replaceFirst(RegExp(r'0+$'), '')
          .replaceFirst(RegExp(r'\.$'), '');
