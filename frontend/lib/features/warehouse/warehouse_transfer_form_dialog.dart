import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';
import '../production/production_models.dart';
import 'warehouse_models.dart';

class WarehouseTransferFormDialog extends StatefulWidget {
  const WarehouseTransferFormDialog({super.key, required this.api});

  final ApiClient api;

  @override
  State<WarehouseTransferFormDialog> createState() =>
      _WarehouseTransferFormDialogState();
}

class _WarehouseTransferFormDialogState
    extends State<WarehouseTransferFormDialog> {
  final _key = GlobalKey<FormState>();
  final _quantity = TextEditingController();
  final _document = TextEditingController();
  final _notes = TextEditingController();
  DateTime _date = DateTime.now();
  List<WarehouseStockLot> _lots = [];
  List<ProductionProcessModel> _processes = [];
  List<Map<String, dynamic>> _finishedLocations = [];
  WarehouseStockLot? _lot;
  String _destinationType = 'wip';
  String? _processCode;
  String? _locationCode;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _quantity.dispose();
    _document.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final responses = await Future.wait([
        widget.api.getJson('/warehouse/stock-lots?page=1&size=100'),
        widget.api.getJson(
          '/warehouse/production-destinations?page=1&size=100&active_only=true',
        ),
        widget.api.getJson('/master-data/storage-locations?page=1&size=100'),
      ]);
      if (!mounted) return;
      setState(() {
        _lots = (responses[0]['items'] as List)
            .map(
              (item) =>
                  WarehouseStockLot.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _processes = (responses[1]['items'] as List)
            .map(
              (item) =>
                  ProductionProcessModel.fromJson(item as Map<String, dynamic>),
            )
            .where((item) => item.type == 'production')
            .toList();
        _finishedLocations = (responses[2]['items'] as List)
            .cast<Map<String, dynamic>>()
            .where((item) => item['storage_type'] == 'finished_goods')
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

  Future<void> _save() async {
    if (!_key.currentState!.validate() || _lot == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.postJson('/warehouse', {
        'transfer_date': _apiDate(_date),
        'source_lot_id': _lot!.id,
        'quantity': double.parse(_quantity.text),
        'destination_type': _destinationType,
        'destination_process_code': _destinationType == 'wip'
            ? _processCode
            : null,
        'destination_location_code': _destinationType == 'finished_goods'
            ? _locationCode
            : null,
        'document_number': _document.text.trim().isEmpty
            ? null
            : _document.text.trim(),
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
      constraints: const BoxConstraints(maxWidth: 760, maxHeight: 760),
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
                            'Create Storage Material Transfer',
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                        IconButton(
                          onPressed: () => Navigator.pop(context),
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
                    InkWell(
                      onTap: _pickDate,
                      child: InputDecorator(
                        decoration: const InputDecoration(
                          labelText: 'Transfer Date *',
                        ),
                        child: Text(_displayDate(_date)),
                      ),
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<int>(
                      decoration: const InputDecoration(
                        labelText: 'Product / Lot / Source Location *',
                      ),
                      isExpanded: true,
                      items: _lots
                          .map(
                            (lot) => DropdownMenuItem(
                              value: lot.id,
                              child: Text(
                                '${lot.productCode} — ${lot.description} — Lot ${lot.lotNumber} — ${_number(lot.quantity)} ${unitLabel(lot.unit)}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (id) {
                        setState(() {
                          _lot = _lots
                              .where((item) => item.id == id)
                              .firstOrNull;
                          _processCode = null;
                          _locationCode = null;
                        });
                      },
                      validator: (value) =>
                          value == null ? 'Source Lot is required' : null,
                    ),
                    if (_lot != null) ...[
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          _summary('Plant', _lot!.plantName),
                          _summary('Description', _lot!.description),
                          _summary(
                            'Before Process',
                            '${_lot!.storageName} — ${_lot!.locationName}',
                          ),
                          _summary(
                            'Available',
                            '${_number(_lot!.quantity)} ${unitLabel(_lot!.unit)}',
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _quantity,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        labelText: 'Quantity (${_lot?.unit ?? '-'}) *',
                      ),
                      validator: (value) {
                        final parsed = double.tryParse(value ?? '');
                        if (parsed == null || parsed <= 0) {
                          return 'Enter a valid Quantity';
                        }
                        if (_lot != null && parsed > _lot!.quantity) {
                          return 'Quantity exceeds available stock';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: _destinationType,
                      decoration: const InputDecoration(
                        labelText: 'After Process Type *',
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'wip',
                          child: Text('Production WIP'),
                        ),
                        DropdownMenuItem(
                          value: 'finished_goods',
                          child: Text('Finished Goods'),
                        ),
                      ],
                      onChanged: (value) => setState(() {
                        _destinationType = value ?? 'wip';
                        _processCode = null;
                        _locationCode = null;
                      }),
                    ),
                    const SizedBox(height: 14),
                    if (_destinationType == 'wip')
                      DropdownButtonFormField<String>(
                        initialValue: _processCode,
                        decoration: const InputDecoration(
                          labelText: 'After Process *',
                        ),
                        isExpanded: true,
                        items: _processes
                            .where(
                              (item) =>
                                  _lot == null ||
                                  item.plantCode == _lot!.plantCode,
                            )
                            .map(
                              (item) => DropdownMenuItem(
                                value: item.code,
                                child: Text('${item.code} — ${item.name}'),
                              ),
                            )
                            .toList(),
                        onChanged: (value) =>
                            setState(() => _processCode = value),
                        validator: (value) =>
                            value == null ? 'WIP Process is required' : null,
                      )
                    else
                      DropdownButtonFormField<String>(
                        initialValue: _locationCode,
                        decoration: const InputDecoration(
                          labelText: 'Finished Goods Location *',
                        ),
                        isExpanded: true,
                        items: _finishedLocations
                            .where(
                              (item) =>
                                  _lot == null ||
                                  item['plant_code'] == _lot!.plantCode,
                            )
                            .map(
                              (item) => DropdownMenuItem(
                                value: item['code'].toString(),
                                child: Text(
                                  '${item['storage_name']} — ${item['name']}',
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (value) =>
                            setState(() => _locationCode = value),
                        validator: (value) => value == null
                            ? 'Finished Goods Location is required'
                            : null,
                      ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _document,
                      decoration: const InputDecoration(
                        labelText: 'Document Number',
                      ),
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: _notes,
                      minLines: 2,
                      maxLines: 4,
                      decoration: const InputDecoration(labelText: 'Notes'),
                    ),
                    const SizedBox(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        TextButton(
                          onPressed: _saving
                              ? null
                              : () => Navigator.pop(context),
                          child: const Text('Cancel'),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: _saving ? null : _save,
                          icon: _saving
                              ? const SizedBox.square(
                                  dimension: 16,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.save_outlined),
                          label: const Text('Post Transfer'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
    ),
  );

  Widget _summary(String label, String value) => SizedBox(
    width: 320,
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

  String _apiDate(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  String _displayDate(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
  String _number(double value) => value == value.truncateToDouble()
      ? value.toInt().toString()
      : value.toString();
}
