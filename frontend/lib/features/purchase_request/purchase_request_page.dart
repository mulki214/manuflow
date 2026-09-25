import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';

class PurchaseRequestPage extends StatefulWidget {
  const PurchaseRequestPage({super.key, required this.auth});
  final AuthController auth;
  @override
  State<PurchaseRequestPage> createState() => _PurchaseRequestPageState();
}

class _PurchaseRequestPageState extends State<PurchaseRequestPage> {
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _products = [];
  List<Map<String, dynamic>> _plants = [];
  String? _error;
  bool _loading = true;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final responses = await Future.wait([
        widget.auth.api.getJson('/purchase-requests?page=1&size=100'),
        widget.auth.api.getJson('/master-data/products?page=1&size=100'),
        widget.auth.api.getJson('/master-data/plants?page=1&size=100'),
      ]);
      if (mounted) {
        setState(() {
          _items = (responses[0]['items'] as List).cast<Map<String, dynamic>>();
          _products = (responses[1]['items'] as List)
              .cast<Map<String, dynamic>>()
              .where((product) => product['is_active'] != false)
              .toList();
          _plants = (responses[2]['items'] as List)
              .cast<Map<String, dynamic>>();
        });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pdf(Map<String, dynamic> pr) async {
    final n = pr['request_number'].toString();
    try {
      final b = await widget.auth.api.getBytes(
        '/purchase-requests/${Uri.encodeComponent(n)}/pdf',
      );
      await FileSaver.instance.saveFile(
        name: 'purchase-request-$n',
        bytes: b,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Purchase Request $n PDF downloaded')),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  String _plantLabel(String code) {
    for (final plant in _plants) {
      if (plant['code']?.toString() == code) {
        return '${plant['code']} — ${plant['name']}';
      }
    }
    return code;
  }

  Future<void> _refreshPlants() async {
    try {
      final response = await widget.auth.api.getJson(
        '/master-data/plants?page=1&size=100',
      );
      if (mounted) {
        setState(() {
          _plants = (response['items'] as List).cast<Map<String, dynamic>>();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Unable to load Receiving Plants: ${exception.message}',
            ),
          ),
        );
      }
    }
  }

  Future<void> _refreshProducts() async {
    try {
      final response = await widget.auth.api.getJson(
        '/master-data/products?page=1&size=100',
      );
      if (mounted) {
        setState(() {
          _products = (response['items'] as List)
              .cast<Map<String, dynamic>>()
              .where((product) => product['is_active'] != false)
              .toList();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Unable to load Products: ${exception.message}'),
          ),
        );
      }
    }
  }

  Future<void> _review(Map<String, dynamic> pr, bool approve) async {
    String reason = '';
    if (!approve) {
      final c = TextEditingController();
      reason =
          await showDialog<String>(
            context: context,
            builder: (x) => AlertDialog(
              title: const Text('Reject Purchase Request'),
              content: TextField(
                controller: c,
                decoration: const InputDecoration(labelText: 'Reason *'),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(x),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(x, c.text),
                  child: const Text('Reject'),
                ),
              ],
            ),
          ) ??
          '';
      if (reason.trim().length < 3) return;
    }
    try {
      await widget.auth.api.postJson(
        '/purchase-requests/${pr['request_number']}/${approve ? 'approve' : 'reject'}',
        approve ? {} : {'reason': reason.trim()},
      );
      await _load();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.purchaseRequest,
    title: 'Purchase Request',
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _form(context),
      icon: const Icon(Icons.add),
      label: const Text('Create Request'),
    ),
    body: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Purchase Requests',
              style: Theme.of(
                context,
              ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              '${_items.length} request records',
              style: const TextStyle(color: Color(0xFF667085)),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                  ? Center(child: Text(_error!))
                  : ListView.separated(
                      itemCount: _items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, i) {
                        final p = _items[i];
                        return Card(
                          child: ListTile(
                            title: Text(
                              '${p['request_number']} — ${p['created_by_name']}',
                            ),
                            subtitle: Text(
                              '${p['status']} • ${(p['items'] as List).length} product(s)\n${(p['items'] as List).map((item) => '${item['product_code']} — ${item['description']}').join('\n')}',
                            ),
                            isThreeLine: true,
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: 'Download PDF',
                                  onPressed: () => _pdf(p),
                                  icon: const Icon(
                                    Icons.picture_as_pdf_outlined,
                                  ),
                                ),
                                if (p['can_edit'] == true ||
                                    p['can_review'] == true)
                                  PopupMenuButton<String>(
                                    onSelected: (a) {
                                      if (a == 'edit') {
                                        _form(context, existing: p);
                                      }
                                      if (a == 'approve') {
                                        _review(p, true);
                                      }
                                      if (a == 'reject') {
                                        _review(p, false);
                                      }
                                    },
                                    itemBuilder: (_) => [
                                      if (p['can_edit'] == true)
                                        const PopupMenuItem(
                                          value: 'edit',
                                          child: Text('Edit'),
                                        ),
                                      if (p['can_review'] == true) ...[
                                        const PopupMenuItem(
                                          value: 'approve',
                                          child: Text('Approve'),
                                        ),
                                        const PopupMenuItem(
                                          value: 'reject',
                                          child: Text('Reject'),
                                        ),
                                      ],
                                    ],
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    ),
  );
  Future<void> _form(
    BuildContext context, {
    Map<String, dynamic>? existing,
  }) async {
    final existingItems = (existing?['items'] as List? ?? const []);
    final lines = existingItems.isEmpty
        ? [_PurchaseRequestLine()]
        : existingItems
              .map(
                (item) =>
                    _PurchaseRequestLine.fromJson(item as Map<String, dynamic>),
              )
              .toList();
    final notes = TextEditingController(
      text: existing?['notes']?.toString() ?? '',
    );
    String? plantCode = existing?['delivery_plant_code']?.toString();
    var requestedDeliveryDate =
        DateTime.tryParse(
          existing?['requested_delivery_date']?.toString() ?? '',
        ) ??
        DateTime.now();
    final ok = await showDialog<bool>(
      context: context,
      builder: (x) => StatefulBuilder(
        builder: (x, setDialogState) => AlertDialog(
          title: Text(
            existing == null
                ? 'Create Purchase Request'
                : 'Edit Purchase Request',
          ),
          content: SizedBox(
            width: 560,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () async {
                      if (_plants.isEmpty) {
                        await _refreshPlants();
                      }
                      if (!x.mounted) return;
                      if (_plants.isEmpty) {
                        ScaffoldMessenger.of(x).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'No Receiving Plant is available. Create a Plant in Master Data first.',
                            ),
                          ),
                        );
                        return;
                      }
                      final selected = await showDialog<String>(
                        context: x,
                        builder: (pickerContext) => AlertDialog(
                          title: const Text('Select Receiving Plant'),
                          content: SizedBox(
                            width: 420,
                            child: ListView.builder(
                              shrinkWrap: true,
                              itemCount: _plants.length,
                              itemBuilder: (_, index) {
                                final plant = _plants[index];
                                final code = plant['code'].toString();
                                return ListTile(
                                  title: Text(
                                    '${plant['code']} — ${plant['name']}',
                                  ),
                                  trailing: code == plantCode
                                      ? const Icon(Icons.check)
                                      : null,
                                  onTap: () =>
                                      Navigator.pop(pickerContext, code),
                                );
                              },
                            ),
                          ),
                        ),
                      );
                      if (selected != null) {
                        setDialogState(() => plantCode = selected);
                      }
                    },
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Receiving Plant *',
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              plantCode == null
                                  ? 'Select Receiving Plant'
                                  : _plantLabel(plantCode!),
                            ),
                          ),
                          const Icon(Icons.arrow_drop_down),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Expected Arrival Date *'),
                    subtitle: Text(
                      '${requestedDeliveryDate.year.toString().padLeft(4, '0')}-${requestedDeliveryDate.month.toString().padLeft(2, '0')}-${requestedDeliveryDate.day.toString().padLeft(2, '0')}',
                    ),
                    trailing: const Icon(Icons.calendar_today_outlined),
                    onTap: () async {
                      final value = await showDatePicker(
                        context: x,
                        initialDate: requestedDeliveryDate,
                        firstDate: DateTime.now(),
                        lastDate: DateTime(2200),
                      );
                      if (value != null) {
                        setDialogState(() => requestedDeliveryDate = value);
                      }
                    },
                  ),
                  const Divider(),
                  const Text('Requested Products'),
                  const SizedBox(height: 8),
                  for (var index = 0; index < lines.length; index++) ...[
                    _PurchaseRequestLineFields(
                      index: index,
                      line: lines[index],
                      products: _products,
                      onSelectProduct: () async {
                        if (_products.isEmpty) await _refreshProducts();
                        if (!x.mounted) return;
                        if (_products.isEmpty) {
                          ScaffoldMessenger.of(x).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'No Product is available in Master Data.',
                              ),
                            ),
                          );
                          return;
                        }
                        final selected = await showDialog<String>(
                          context: x,
                          builder: (pickerContext) => AlertDialog(
                            title: const Text('Select Product'),
                            content: SizedBox(
                              width: 520,
                              child: ListView.builder(
                                shrinkWrap: true,
                                itemCount: _products.length,
                                itemBuilder: (_, productIndex) {
                                  final product = _products[productIndex];
                                  final code = product['code'].toString();
                                  return ListTile(
                                    title: Text(
                                      '${product['code']} — ${product['description']}',
                                    ),
                                    trailing: code == lines[index].productCode
                                        ? const Icon(Icons.check)
                                        : null,
                                    onTap: () =>
                                        Navigator.pop(pickerContext, code),
                                  );
                                },
                              ),
                            ),
                          ),
                        );
                        if (selected != null) {
                          setDialogState(
                            () => lines[index].productCode = selected,
                          );
                        }
                      },
                      canRemove: lines.length > 1,
                      onRemove: () => setDialogState(() {
                        lines.removeAt(index).dispose();
                      }),
                    ),
                    const SizedBox(height: 12),
                  ],
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: () => setDialogState(
                        () => lines.add(_PurchaseRequestLine()),
                      ),
                      icon: const Icon(Icons.add),
                      label: const Text('Add Product'),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: notes,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Notes'),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(x),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () async {
                if (plantCode == null ||
                    lines.any(
                      (line) =>
                          line.productCode == null ||
                          line.quantity.text.trim().isEmpty ||
                          line.unit == null,
                    )) {
                  ScaffoldMessenger.of(x).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Complete product code, quantity, and unit for every line',
                      ),
                    ),
                  );
                  return;
                }
                try {
                  final body = {
                    'request_date': DateTime.now().toIso8601String().substring(
                      0,
                      10,
                    ),
                    'requested_delivery_date': requestedDeliveryDate
                        .toIso8601String()
                        .substring(0, 10),
                    'delivery_plant_code': plantCode,
                    'notes': notes.text,
                    'items': [
                      for (final line in lines)
                        {
                          'product_code': line.productCode,
                          'quantity': line.quantity.text.trim(),
                          'unit': line.unit,
                          'remark': line.remark.text.trim(),
                        },
                    ],
                  };
                  if (existing == null) {
                    await widget.auth.api.postJson('/purchase-requests', body);
                  } else {
                    await widget.auth.api.patchJson(
                      '/purchase-requests/${Uri.encodeComponent(existing['request_number'].toString())}',
                      body,
                    );
                  }
                  if (x.mounted) Navigator.pop(x, true);
                } on ApiException catch (e) {
                  if (x.mounted) {
                    ScaffoldMessenger.of(
                      x,
                    ).showSnackBar(SnackBar(content: Text(e.message)));
                  }
                }
              },
              child: const Text('Submit'),
            ),
          ],
        ),
      ),
    );
    for (final line in lines) {
      line.dispose();
    }
    notes.dispose();
    if (ok == true) _load();
  }
}

class _PurchaseRequestLine {
  String? productCode;
  final quantity = TextEditingController();
  String? unit = 'pcs';
  final remark = TextEditingController();

  _PurchaseRequestLine();

  _PurchaseRequestLine.fromJson(Map<String, dynamic> json)
    : productCode = json['product_code']?.toString(),
      unit = json['unit']?.toString() ?? 'pcs' {
    quantity.text = formatQuantity(json['quantity'], unit ?? 'pcs');
    remark.text = json['remark']?.toString() ?? '';
  }

  void dispose() {
    quantity.dispose();
    remark.dispose();
  }
}

class _PurchaseRequestLineFields extends StatelessWidget {
  const _PurchaseRequestLineFields({
    required this.index,
    required this.line,
    required this.products,
    required this.onSelectProduct,
    required this.canRemove,
    required this.onRemove,
  });

  final int index;
  final _PurchaseRequestLine line;
  final List<Map<String, dynamic>> products;
  final Future<void> Function() onSelectProduct;
  final bool canRemove;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) => Card(
    margin: EdgeInsets.zero,
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: Text('Product ${index + 1}')),
              if (canRemove)
                IconButton(
                  tooltip: 'Remove product',
                  onPressed: onRemove,
                  icon: const Icon(Icons.delete_outline),
                ),
            ],
          ),
          InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: onSelectProduct,
            child: InputDecorator(
              decoration: const InputDecoration(labelText: 'Product *'),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      line.productCode == null
                          ? 'Product'
                          : _productLabel(line.productCode!),
                    ),
                  ),
                  const Icon(Icons.arrow_drop_down),
                ],
              ),
            ),
          ),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: line.quantity,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(labelText: 'Quantity *'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: line.unit,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Unit *'),
                  items: const [
                    DropdownMenuItem(value: 'pcs', child: Text('pcs')),
                    DropdownMenuItem(value: 'bar', child: Text('bar')),
                    DropdownMenuItem(value: 'liter', child: Text('liter')),
                    DropdownMenuItem(value: 'pail', child: Text('pail')),
                    DropdownMenuItem(value: 'kg', child: Text('kg')),
                    DropdownMenuItem(value: 'ton', child: Text('ton')),
                    DropdownMenuItem(value: 'gram', child: Text('gram')),
                  ],
                  onChanged: (value) => line.unit = value,
                ),
              ),
            ],
          ),
          TextField(
            controller: line.remark,
            decoration: const InputDecoration(labelText: 'Remark'),
          ),
        ],
      ),
    ),
  );

  String _productLabel(String code) {
    for (final product in products) {
      if (product['code']?.toString() == code) {
        return '${product['code']} — ${product['description']}';
      }
    }
    return code;
  }
}
