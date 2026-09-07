import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';

class ConsumableDispositionDialog extends StatefulWidget {
  const ConsumableDispositionDialog({
    super.key,
    required this.api,
    required this.executionId,
  });
  final ApiClient api;
  final int executionId;

  @override
  State<ConsumableDispositionDialog> createState() =>
      _ConsumableDispositionDialogState();
}

class _ConsumableDispositionDialogState
    extends State<ConsumableDispositionDialog> {
  final _consumed = TextEditingController(text: '0');
  final _waste = TextEditingController(text: '0');
  final _scrap = TextEditingController(text: '0');
  List<Map<String, dynamic>> _lots = [];
  List<Map<String, dynamic>> _locations = [];
  int? _lotId;
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
    _consumed.dispose();
    _waste.dispose();
    _scrap.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await Future.wait([
        widget.api.getJson('/production/stock'),
        widget.api.getJson('/master-data/storage-locations?page=1&size=100'),
      ]);
      if (mounted) {
        setState(() {
          _lots = (data[0] as List).cast<Map<String, dynamic>>();
          _locations = (data[1]['items'] as List).cast<Map<String, dynamic>>();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  double _value(TextEditingController value) =>
      double.tryParse(value.text.trim()) ?? 0;

  Future<void> _save() async {
    if (_lotId == null ||
        _value(_consumed) + _value(_waste) + _value(_scrap) <= 0 ||
        (_value(_scrap) > 0 && _locationCode == null)) {
      setState(
        () => _error =
            'Select a lot, enter a disposition quantity, and select Scrap Location when applicable.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.postJson(
        '/production/executions/${widget.executionId}/consumables',
        {
          'source_lot_id': _lotId,
          'consumed_quantity': _value(_consumed),
          'waste_quantity': _value(_waste),
          'scrap_quantity': _value(_scrap),
          'scrap_storage_location_code': _locationCode,
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
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Record Consumable Disposition'),
    content: SizedBox(
      width: 620,
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              child: Column(
                children: [
                  DropdownButtonFormField<int>(
                    initialValue: _lotId,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Consumable Stock Lot *',
                    ),
                    items: _lots
                        .map(
                          (lot) => DropdownMenuItem<int>(
                            value: lot['lot_id'] as int,
                            child: Text(
                              '${lot['product_code']} — Lot ${lot['lot_number']} — ${lot['quantity']} ${unitLabel(lot['unit'].toString())}',
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) => setState(() => _lotId = value),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(child: _field(_consumed, 'Consumed')),
                      const SizedBox(width: 10),
                      Expanded(child: _field(_waste, 'Waste')),
                      const SizedBox(width: 10),
                      Expanded(child: _field(_scrap, 'Return as Scrap')),
                    ],
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _locationCode,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Scrap Storage Location',
                    ),
                    items: _locations
                        .map(
                          (item) => DropdownMenuItem(
                            value: item['code'].toString(),
                            child: Text('${item['code']} — ${item['name']}'),
                          ),
                        )
                        .toList(),
                    onChanged: (value) => setState(() => _locationCode = value),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Colors.red),
                      ),
                    ),
                ],
              ),
            ),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _saving ? null : _save,
        child: const Text('Save Disposition'),
      ),
    ],
  );

  Widget _field(TextEditingController controller, String label) => TextField(
    controller: controller,
    keyboardType: const TextInputType.numberWithOptions(decimal: true),
    decoration: InputDecoration(labelText: label),
  );
}
