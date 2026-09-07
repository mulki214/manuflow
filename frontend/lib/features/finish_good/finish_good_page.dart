import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/product_qr_label_dialog.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';

class FinishGoodPage extends StatefulWidget {
  const FinishGoodPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<FinishGoodPage> createState() => _FinishGoodPageState();
}

class _FinishGoodPageState extends State<FinishGoodPage> {
  List<Map<String, dynamic>> _queue = [];
  List<Map<String, dynamic>> _history = [];
  List<Map<String, dynamic>> _stockLots = [];
  String _tab = 'queue';
  bool _loading = true;
  String? _error;

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
      final results = await Future.wait([
        widget.auth.api.getJson('/finish-goods/queue'),
        widget.auth.api.getJson('/finish-goods?page=1&size=100'),
        widget.auth.api.getJson('/finish-goods/stock-lots'),
      ]);
      if (!mounted) return;
      setState(() {
        _queue = (results[0] as List).cast<Map<String, dynamic>>();
        _history = (results[1]['items'] as List).cast<Map<String, dynamic>>();
        _stockLots = (results[2] as List).cast<Map<String, dynamic>>();
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to load Finish Good data.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _post(Map<String, dynamic> job) async {
    try {
      final response = await widget.auth.api.getJson(
        '/master-data/storage-locations?page=1&size=100',
      );
      if (!mounted) return;
      final locations = (response['items'] as List)
          .cast<Map<String, dynamic>>()
          .where(
            (item) =>
                item['plant_code'] == job['plant_code'] &&
                item['storage_type'] == 'finished_goods',
          )
          .toList();
      if (locations.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Create a Finished Goods storage location for this plant first.',
            ),
          ),
        );
        return;
      }

      String? locationCode;
      final jobId = job['job_id'];
      final posted = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, setModalState) => AlertDialog(
            title: const Text('Post to Finish Good'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${job['product_code']} • Lot ${job['lot_number']} • '
                  '${job['quantity']} ${unitLabel(job['unit'].toString())}',
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  decoration: const InputDecoration(
                    labelText: 'Finished Goods Location *',
                  ),
                  items: locations
                      .map(
                        (item) => DropdownMenuItem(
                          value: item['code'].toString(),
                          child: Text('${item['code']} — ${item['name']}'),
                        ),
                      )
                      .toList(),
                  onChanged: (value) =>
                      setModalState(() => locationCode = value),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: locationCode == null
                    ? null
                    : () async {
                        try {
                          await widget.auth.api
                              .postJson('/finish-goods/queue/$jobId/post', {
                                'receipt_date': DateTime.now()
                                    .toIso8601String()
                                    .substring(0, 10),
                                'storage_location_code': locationCode,
                                'notes': '',
                              });
                          if (dialogContext.mounted) {
                            Navigator.pop(dialogContext, true);
                          }
                        } on ApiException catch (exception) {
                          if (dialogContext.mounted) {
                            ScaffoldMessenger.of(dialogContext).showSnackBar(
                              SnackBar(content: Text(exception.message)),
                            );
                          }
                        }
                      },
                child: const Text('Post'),
              ),
            ],
          ),
        ),
      );
      if (posted == true) {
        await _load();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Finish Good stock posted.')),
          );
        }
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  Future<void> _reverse(Map<String, dynamic> receipt) async {
    final reason = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Reverse ${receipt['receipt_number']}?'),
        content: TextField(
          controller: reason,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Reason *'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, reason.text.trim()),
            child: const Text('Reverse'),
          ),
        ],
      ),
    );
    reason.dispose();
    if (value == null || value.length < 3) return;
    try {
      await widget.auth.api.postJson(
        '/finish-goods/${receipt['receipt_number']}/reverse',
        {'reason': value},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Finish Good posting reversed.')),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = switch (_tab) {
      'queue' => _queue,
      'history' => _history,
      _ => _stockLots,
    };
    return AppModuleScaffold(
      auth: widget.auth,
      activeModule: AppModule.finishGood,
      title: 'Finish Good',
      actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Finish Good',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                _tab == 'queue'
                    ? '${_queue.length} QC-passed lots waiting to be posted'
                    : _tab == 'history'
                    ? '${_history.length} posting records'
                    : '${_stockLots.length} lots currently in Finished Goods',
                style: const TextStyle(color: Color(0xFF667085)),
              ),
              const SizedBox(height: 16),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'queue', label: Text('QC Pass Queue')),
                  ButtonSegment(
                    value: 'history',
                    label: Text('Posting History'),
                  ),
                  ButtonSegment(
                    value: 'stock',
                    label: Text('Finished Goods Stock'),
                  ),
                ],
                selected: {_tab},
                onSelectionChanged: (value) =>
                    setState(() => _tab = value.first),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _error != null
                    ? Center(child: Text(_error!))
                    : items.isEmpty
                    ? Center(
                        child: Text(
                          _tab == 'queue'
                              ? 'No QC-passed WIP lots are waiting.'
                              : _tab == 'history'
                              ? 'No Finish Good postings found.'
                              : 'No Finished Goods stock is available.',
                        ),
                      )
                    : ListView.separated(
                        itemCount: items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (_, index) {
                          final item = items[index];
                          final title = _tab == 'queue'
                              ? '${item['product_code']} — Lot ${item['lot_number']}'
                              : _tab == 'history'
                              ? item['receipt_number'].toString()
                              : '${item['product_code']} — ${item['product_name']} — Lot ${item['lot_number']}';
                          return Card(
                            child: ListTile(
                              title: Text(title),
                              subtitle: Text(
                                'Qty ${item['quantity']} ${unitLabel(item['unit'].toString())} • '
                                'Plant ${item['plant_code']}'
                                '${_tab == 'stock' ? ' • ${item['storage_name']} — ${item['storage_location_name']}' : ''}',
                              ),
                              trailing: _tab == 'stock'
                                  ? IconButton(
                                      tooltip: 'Download lot QR',
                                      icon: const Icon(
                                        Icons.qr_code_2_outlined,
                                      ),
                                      onPressed: () => showDialog<void>(
                                        context: context,
                                        builder: (_) => ProductQrLabelDialog(
                                          productCode: item['product_code']
                                              .toString(),
                                          productName: item['product_name']
                                              .toString(),
                                          lotId: item['lot_id'] as int?,
                                          lotNumber: item['lot_number']
                                              .toString(),
                                        ),
                                      ),
                                    )
                                  : _tab == 'queue'
                                  ? FilledButton(
                                      onPressed: () => _post(item),
                                      child: const Text('Post'),
                                    )
                                  : _tab == 'history' &&
                                        item['can_reverse'] == true
                                  ? OutlinedButton(
                                      onPressed: () => _reverse(item),
                                      child: const Text('Reverse'),
                                    )
                                  : _tab == 'history'
                                  ? Chip(
                                      label: Text(
                                        item['status'].toString().toUpperCase(),
                                      ),
                                    )
                                  : null,
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
  }
}
