import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart';
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
                                PopupMenuButton<String>(
                                  onSelected: (a) {
                                    if (a == 'approve') _review(p, true);
                                    if (a == 'reject') _review(p, false);
                                  },
                                  itemBuilder: (_) => [
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
  Future<void> _form(BuildContext context) async {
    final lines = [_PurchaseRequestLine()];
    final notes = TextEditingController();
    String? plantCode;
    var requestedDeliveryDate = DateTime.now();
    final ok = await showDialog<bool>(
      context: context,
      builder: (x) => StatefulBuilder(
        builder: (x, setDialogState) => AlertDialog(
          title: const Text('Create Purchase Request'),
          content: SizedBox(
            width: 560,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: _plants.isEmpty
                        ? () => ScaffoldMessenger.of(x).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'No Receiving Plant is available. Create a Plant in Master Data first.',
                              ),
                            ),
                          )
                        : () async {
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
                      onProductChanged: (value) => setDialogState(() {
                        lines[index].productCode = value;
                      }),
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
                  await widget.auth.api.postJson('/purchase-requests', {
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
                  });
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
    required this.onProductChanged,
    required this.canRemove,
    required this.onRemove,
  });

  final int index;
  final _PurchaseRequestLine line;
  final List<Map<String, dynamic>> products;
  final ValueChanged<String?> onProductChanged;
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
          DropdownButtonFormField<String>(
            initialValue: line.productCode,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Product *'),
            hint: const Text('Select product from Master Data'),
            items: products
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
            onChanged: onProductChanged,
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
}
