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
                        trailing: PopupMenuButton<String>(
                          onSelected: (a) {
                            if (a == 'pdf') _pdf(p);
                            if (a == 'approve') _review(p, true);
                            if (a == 'reject') _review(p, false);
                          },
                          itemBuilder: (_) => [
                            const PopupMenuItem(
                              value: 'pdf',
                              child: Text('Download PDF'),
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
                      );
                    },
                  ),
          ),
        ],
      ),
    ),
  );
  Future<void> _form(BuildContext context) async {
    final product = TextEditingController(),
        qty = TextEditingController(),
        unit = TextEditingController(text: 'pcs'),
        notes = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (x) => AlertDialog(
        title: const Text('Create Purchase Request'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: product,
                decoration: const InputDecoration(labelText: 'Product Code *'),
              ),
              TextField(
                controller: qty,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Quantity *'),
              ),
              TextField(
                controller: unit,
                decoration: const InputDecoration(labelText: 'Unit *'),
              ),
              TextField(
                controller: notes,
                decoration: const InputDecoration(labelText: 'Notes'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(x),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              try {
                await widget.auth.api.postJson('/purchase-requests', {
                  'request_date': DateTime.now().toIso8601String().substring(
                    0,
                    10,
                  ),
                  'notes': notes.text,
                  'items': [
                    {
                      'product_code': product.text.trim(),
                      'quantity': qty.text,
                      'unit': unit.text.trim(),
                      'remark': '',
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
    );
    if (ok == true) _load();
  }
}
