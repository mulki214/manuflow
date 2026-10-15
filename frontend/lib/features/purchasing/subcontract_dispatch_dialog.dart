import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/searchable_select_field.dart';
import '../../shared/units.dart';
import 'purchase_order_models.dart';

class SubcontractDispatchDialog extends StatefulWidget {
  const SubcontractDispatchDialog({
    super.key,
    required this.api,
    required this.order,
  });

  final ApiClient api;
  final PurchaseOrderModel order;

  @override
  State<SubcontractDispatchDialog> createState() =>
      _SubcontractDispatchDialogState();
}

class _SubcontractDispatchDialogState extends State<SubcontractDispatchDialog> {
  final _formKey = GlobalKey<FormState>();
  final _quantity = TextEditingController();
  final _expectedOutput = TextEditingController();
  final _notes = TextEditingController();
  List<Map<String, dynamic>> _lots = [];
  int? _itemId;
  Map<String, dynamic>? _source;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  PurchaseOrderItemModel? get _item {
    for (final item in widget.order.items) {
      if (item.id == _itemId) return item;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _quantity.dispose();
    _expectedOutput.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final result = await widget.api.getJson(
        '/purchasing/subcontract-source-lots',
      );
      if (!mounted) return;
      setState(
        () => _lots = List<Map<String, dynamic>>.from(result['items'] as List),
      );
    } on ApiException catch (error) {
      _error = error.message;
    } catch (_) {
      _error = 'Unable to load available stock lots.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final selected = _item;
    if (selected == null || _source == null) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.postJson(
        '/purchasing/${Uri.encodeComponent(widget.order.poNumber)}/subcontract-dispatches',
        {
          'purchase_order_item_id': selected.id,
          'source_lot_id': _source!['source_type'] == 'stock_lot'
              ? _source!['source_id']
              : null,
          'source_wip_job_id': _source!['source_type'] == 'wip_job'
              ? _source!['source_id']
              : null,
          'quantity': double.parse(_quantity.text),
          'expected_output_quantity': double.parse(_expectedOutput.text),
          'source_process_code':
              _source?['process_code']?.toString() ?? selected.processFromCode,
          'process_to_code': selected.processToCode,
          'notes': _notes.text.trim(),
        },
      );
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String? _positive(String? raw, String label, String? unit) {
    final value = double.tryParse(raw ?? '');
    if (value == null || value <= 0) return '$label must be greater than zero.';
    if (unit != null &&
        isDiscreteUnit(unit) &&
        value != value.roundToDouble()) {
      return '$label must be a whole number for $unit.';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Dispatch to Subcontractor'),
      content: SizedBox(
        width: 620,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : Form(
                key: _formKey,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (_error != null) ...[
                        Text(
                          _error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                        const SizedBox(height: 12),
                      ],
                      Text(
                        'PO ${widget.order.poNumber} • ${widget.order.salesOrderNumber ?? '-'}',
                      ),
                      const SizedBox(height: 16),
                      SearchableSelectField<int>(
                        value: _itemId,
                        labelText: 'Subcontract PO Product *',
                        searchHint: 'Search product',
                        options: widget.order.items
                            .map(
                              (item) => SearchableSelectOption(
                                value: item.id,
                                label:
                                    '${item.partName} — ${item.outstandingQuantity} ${item.unit}',
                                searchTerms: [
                                  item.productCode,
                                  item.partName,
                                  item.description,
                                ],
                              ),
                            )
                            .toList(),
                        onChanged: (value) => setState(() {
                          _itemId = value;
                          _expectedOutput.clear();
                        }),
                        validator: (value) =>
                            value == null ? 'Select the PO product.' : null,
                      ),
                      const SizedBox(height: 12),
                      SearchableSelectField<String>(
                        value: _source == null ? null : _sourceKey(_source!),
                        labelText: 'Source Stock Lot or WIP *',
                        searchHint: 'Search product or lot',
                        options: _lots
                            .map(
                              (lot) => SearchableSelectOption(
                                value: _sourceKey(lot),
                                label:
                                    '${lot['product_name']} — ${lot['source_type'] == 'wip_job' ? 'WIP' : 'Lot'} ${lot['lot_number']} • ${formatQuantity(lot['quantity'], lot['unit'].toString())} ${unitLabel(lot['unit'].toString())}${lot['process_code'] == null ? '' : ' • ${lot['process_code']}'}',
                                searchTerms: [
                                  lot['product_code'].toString(),
                                  lot['product_name'].toString(),
                                  lot['lot_number'].toString(),
                                  lot['process_code']?.toString() ?? '',
                                ],
                              ),
                            )
                            .toList(),
                        onChanged: (value) => setState(() {
                          _source = _findSource(value);
                          _quantity.clear();
                        }),
                        validator: (value) =>
                            value == null ? 'Select an available lot.' : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _quantity,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Quantity sent *',
                          helperText: 'Uses the selected lot unit.',
                        ),
                        validator: (value) => _positive(
                          value,
                          'Quantity sent',
                          _source?['unit']?.toString(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _expectedOutput,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: InputDecoration(
                          labelText:
                              'Expected returned quantity *${_item == null ? '' : ' (${_item!.unit})'}',
                        ),
                        validator: (value) => _positive(
                          value,
                          'Expected returned quantity',
                          _item?.unit,
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _notes,
                        minLines: 2,
                        maxLines: 4,
                        decoration: const InputDecoration(labelText: 'Notes'),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Returned subcontract output must be posted through Receiving → Subcontract Return.',
                      ),
                    ],
                  ),
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          onPressed: _saving || _loading ? null : _submit,
          icon: _saving
              ? const SizedBox.square(
                  dimension: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.local_shipping_outlined),
          label: const Text('Dispatch'),
        ),
      ],
    );
  }

  String _sourceKey(Map<String, dynamic> source) =>
      '${source['source_type']}:${source['source_id']}';

  Map<String, dynamic>? _findSource(String? key) {
    for (final source in _lots) {
      if (_sourceKey(source) == key) return source;
    }
    return null;
  }
}
