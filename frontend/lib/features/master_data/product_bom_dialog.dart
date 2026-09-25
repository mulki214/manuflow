import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/units.dart';

class ProductBomDialog extends StatefulWidget {
  const ProductBomDialog({
    super.key,
    required this.api,
    required this.productCode,
  });

  final ApiClient api;
  final String productCode;

  @override
  State<ProductBomDialog> createState() => _ProductBomDialogState();
}

class _ProductBomDialogState extends State<ProductBomDialog> {
  final List<_BomLine> _lines = [];
  final _outputQuantity = TextEditingController(text: '1');
  List<Map<String, dynamic>> _products = [];
  String _outputUnit = 'pcs';
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
    _outputQuantity.dispose();
    for (final line in _lines) {
      line.quantity.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.api.getJson('/master-data/products?size=100'),
        widget.api.getJson('/master-data/products/${widget.productCode}/bom'),
      ]);
      final productResponse = values[0] as Map<String, dynamic>;
      final bomResponse = values[1] as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _products = (productResponse['items'] as List)
            .cast<Map<String, dynamic>>()
            .where((product) => product['category'] != 'finished_good')
            .toList();
        _outputUnit = bomResponse['output_unit']?.toString() ?? 'pcs';
        _outputQuantity.text = formatQuantity(
          bomResponse['output_quantity'] ?? 1,
          _outputUnit,
        );
        for (final item
            in (bomResponse['items'] as List).cast<Map<String, dynamic>>()) {
          _lines.add(
            _BomLine(
              productCode: item['material_product_code'].toString(),
              unit: item['unit'].toString(),
              quantity: TextEditingController(
                text: formatQuantity(item['quantity'], item['unit'].toString()),
              ),
            ),
          );
        }
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _addLine() => setState(() => _lines.add(_BomLine()));

  void _removeLine(int index) {
    final line = _lines.removeAt(index);
    line.quantity.dispose();
    setState(() {});
  }

  Future<void> _save() async {
    if (quantityValidationError(
          _outputQuantity.text.replaceAll(',', '.'),
          _outputUnit,
        ) !=
        null) {
      setState(() => _error = 'Output per batch must be valid for its unit.');
      return;
    }
    final codes = <String>{};
    for (final line in _lines) {
      if (line.productCode == null ||
          quantityValidationError(
                line.quantity.text.replaceAll(',', '.'),
                line.unit,
              ) !=
              null ||
          !codes.add(line.productCode!)) {
        setState(
          () => _error =
              'Every line needs a unique material and a valid quantity for its unit.',
        );
        return;
      }
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.putJson(
        '/master-data/products/${widget.productCode}/bom',
        {
          'output_quantity': num.parse(
            _outputQuantity.text.replaceAll(',', '.'),
          ),
          'output_unit': _outputUnit,
          'items': _lines
              .map(
                (line) => {
                  'material_product_code': line.productCode,
                  'quantity': num.parse(
                    line.quantity.text.replaceAll(',', '.'),
                  ),
                  'unit': line.unit,
                },
              )
              .toList(),
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
  Widget build(BuildContext context) => Dialog(
    insetPadding: const EdgeInsets.all(16),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 760, maxHeight: 760),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Bill of Materials — ${widget.productCode}',
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
                  const SizedBox(height: 8),
                  const Text(
                    'Define the output per batch, then the input material or WIP required.',
                    style: TextStyle(color: Color(0xFF667085)),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _outputQuantity,
                          keyboardType: TextInputType.numberWithOptions(
                            decimal: !isDiscreteUnit(_outputUnit),
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Output per BOM Batch',
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      SizedBox(
                        width: 120,
                        child: DropdownButtonFormField<String>(
                          initialValue: _outputUnit,
                          decoration: const InputDecoration(
                            labelText: 'Output Unit',
                          ),
                          items: inventoryUnits
                              .map(
                                (unit) => DropdownMenuItem(
                                  value: unit,
                                  child: Text(unitLabel(unit)),
                                ),
                              )
                              .toList(),
                          onChanged: (value) => setState(
                            () => _outputUnit = value ?? _outputUnit,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Expanded(
                    child: _lines.isEmpty
                        ? const Center(
                            child: Text(
                              'No material lines. Add one if this product is manufactured.',
                            ),
                          )
                        : ListView.separated(
                            itemCount: _lines.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 10),
                            itemBuilder: (_, index) => _lineEditor(index),
                          ),
                  ),
                  TextButton.icon(
                    onPressed: _saving ? null : _addLine,
                    icon: const Icon(Icons.add),
                    label: const Text('Add Material'),
                  ),
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: _saving
                            ? null
                            : () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 10),
                      FilledButton(
                        onPressed: _saving ? null : _save,
                        child: Text(_saving ? 'Saving...' : 'Save BOM'),
                      ),
                    ],
                  ),
                ],
              ),
      ),
    ),
  );

  Widget _lineEditor(int index) {
    final line = _lines[index];
    return Row(
      children: [
        Expanded(
          flex: 3,
          child: DropdownButtonFormField<String>(
            initialValue:
                _products.any((product) => product['code'] == line.productCode)
                ? line.productCode
                : null,
            decoration: const InputDecoration(labelText: 'Material Product'),
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
            onChanged: (value) => setState(() => line.productCode = value),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: TextField(
            controller: line.quantity,
            keyboardType: TextInputType.numberWithOptions(
              decimal: !isDiscreteUnit(line.unit),
            ),
            decoration: const InputDecoration(labelText: 'Qty'),
          ),
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 100,
          child: DropdownButtonFormField<String>(
            initialValue: line.unit,
            decoration: const InputDecoration(labelText: 'Unit'),
            items: inventoryUnits
                .map(
                  (unit) => DropdownMenuItem(
                    value: unit,
                    child: Text(unitLabel(unit)),
                  ),
                )
                .toList(),
            onChanged: (value) => setState(() => line.unit = value ?? 'pcs'),
          ),
        ),
        IconButton(
          onPressed: () => _removeLine(index),
          icon: const Icon(Icons.delete_outline),
        ),
      ],
    );
  }
}

class _BomLine {
  _BomLine({
    this.productCode,
    this.unit = 'pcs',
    TextEditingController? quantity,
  }) : quantity = quantity ?? TextEditingController();

  String? productCode;
  String unit;
  final TextEditingController quantity;
}
