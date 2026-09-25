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
      final r = await widget.auth.api.getJson(
        '/purchase-requests?page=1&size=100',
      );
      if (mounted) {
        setState(
          () => _items = (r['items'] as List).cast<Map<String, dynamic>>(),
        );
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
    body: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Purchase Requests',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 12),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                ? Center(child: Text(_error!))
                : ListView.separated(
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (_, i) {
                      final p = _items[i];
                      return ListTile(
                        title: Text(
                          '${p['request_number']} — ${p['created_by_name']}',
                        ),
                        subtitle: Text(
                          '${p['status']} • ${(p['items'] as List).length} product(s)',
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              tooltip: 'Download PDF',
                              onPressed: () => _pdf(p),
                              icon: const Icon(Icons.picture_as_pdf_outlined),
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
                      );
                    },
                  ),
          ),
        ],
      ),
    ),
  );
  Future<void> _form(BuildContext context) async {
    final lines = [_PurchaseRequestLine()];
    final notes = TextEditingController();
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
                  const Text('Requested Products'),
                  const SizedBox(height: 8),
                  for (var index = 0; index < lines.length; index++) ...[
                    _PurchaseRequestLineFields(
                      index: index,
                      line: lines[index],
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
                if (lines.any(
                  (line) =>
                      line.product.text.trim().isEmpty ||
                      line.quantity.text.trim().isEmpty ||
                      line.unit.text.trim().isEmpty,
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
                    'notes': notes.text,
                    'items': [
                      for (final line in lines)
                        {
                          'product_code': line.product.text.trim(),
                          'quantity': line.quantity.text.trim(),
                          'unit': line.unit.text.trim(),
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
  final product = TextEditingController();
  final quantity = TextEditingController();
  final unit = TextEditingController(text: 'pcs');
  final remark = TextEditingController();

  void dispose() {
    product.dispose();
    quantity.dispose();
    unit.dispose();
    remark.dispose();
  }
}

class _PurchaseRequestLineFields extends StatelessWidget {
  const _PurchaseRequestLineFields({
    required this.index,
    required this.line,
    required this.canRemove,
    required this.onRemove,
  });

  final int index;
  final _PurchaseRequestLine line;
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
          TextField(
            controller: line.product,
            decoration: const InputDecoration(labelText: 'Product Code *'),
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
                child: TextField(
                  controller: line.unit,
                  decoration: const InputDecoration(labelText: 'Unit *'),
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
