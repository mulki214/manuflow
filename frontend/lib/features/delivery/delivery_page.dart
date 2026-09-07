import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_module_scaffold.dart';
import '../../shared/app_sidebar.dart' show AppModule;
import '../../shared/mobile_product_scanner.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';

class DeliveryPage extends StatefulWidget {
  const DeliveryPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<DeliveryPage> createState() => _DeliveryPageState();
}

class _DeliveryPageState extends State<DeliveryPage> {
  final _search = TextEditingController();
  List<Map<String, dynamic>> _records = [];
  bool _loading = true;
  String? _error;
  String? _status;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final query = [
        'page=1',
        'size=100',
        if (_search.text.trim().isNotEmpty)
          'search=${Uri.encodeQueryComponent(_search.text.trim())}',
        if (_status != null) 'status=$_status',
      ].join('&');
      final response = await widget.auth.api.getJson('/delivery?$query');
      if (mounted) {
        setState(
          () => _records = (response['items'] as List)
              .cast<Map<String, dynamic>>(),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to load deliveries.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final posted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => DeliveryFormDialog(auth: widget.auth),
    );
    if (posted == true) {
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Delivery marked as dispatched. Confirm arrival to update Sales Order fulfillment.',
            ),
          ),
        );
      }
    }
  }

  Future<void> _reverse(Map<String, dynamic> record) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Reverse ${record['delivery_number']}?'),
        content: TextField(
          controller: controller,
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
            onPressed: () =>
                Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Reverse'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null || reason.length < 3) return;
    try {
      await widget.auth.api.postJson(
        '/delivery/${record['delivery_number']}/reverse',
        {'reason': reason},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Delivery reversed and stock restored.'),
          ),
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

  Future<void> _confirmDelivered(Map<String, dynamic> record) async {
    try {
      await widget.auth.api.postJson(
        '/delivery/${record['delivery_number']}/deliver',
        {},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Delivery confirmed as arrived; SO fulfillment updated.',
            ),
          ),
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
  Widget build(BuildContext context) => AppModuleScaffold(
    auth: widget.auth,
    activeModule: AppModule.delivery,
    title: 'Delivery',
    actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh))],
    floatingActionButton: FloatingActionButton.extended(
      onPressed: _create,
      icon: const Icon(Icons.local_shipping_outlined),
      label: const Text('Post Delivery'),
    ),
    body: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Delivery',
              style: Theme.of(
                context,
              ).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              '${_records.length} delivery records',
              style: const TextStyle(color: Color(0xFF667085)),
            ),
            const SizedBox(height: 20),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _search,
                        onSubmitted: (_) => _load(),
                        decoration: const InputDecoration(
                          labelText:
                              'Search delivery, SO, customer, product, or lot',
                          prefixIcon: Icon(Icons.search),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    DropdownButton<String?>(
                      value: _status,
                      hint: const Text('All status'),
                      items: const [
                        DropdownMenuItem<String?>(
                          value: null,
                          child: Text('All status'),
                        ),
                        DropdownMenuItem(
                          value: 'posted',
                          child: Text('Posted'),
                        ),
                        DropdownMenuItem(
                          value: 'reversed',
                          child: Text('Reversed'),
                        ),
                      ],
                      onChanged: (value) {
                        setState(() => _status = value);
                        _load();
                      },
                    ),
                    IconButton.filledTonal(
                      onPressed: _load,
                      icon: const Icon(Icons.search),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                  ? Center(child: Text(_error!))
                  : _records.isEmpty
                  ? const Center(child: Text('No deliveries have been posted.'))
                  : ListView.separated(
                      itemCount: _records.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (_, index) {
                        final item = _records[index];
                        final canConfirm = item['can_confirm_delivery'] == true;
                        final canReverse = item['can_reverse'] == true;
                        return Card(
                          child: ListTile(
                            title: Text(
                              '${item['delivery_number']} — ${item['customer_name']}',
                            ),
                            subtitle: Text(
                              '${item['sales_order_number']} • ${item['lines'] is List ? (item['lines'] as List).length : 1} item(s)\n'
                              '${(item['lines'] as List? ?? const []).map((line) => '${line['product_code']} / Lot ${line['lot_number']} — ${formatQuantity(line['quantity'], line['unit'].toString())} ${unitLabel(line['unit'].toString())}').join('\n')}',
                            ),
                            isThreeLine: true,
                            trailing: PopupMenuButton<String>(
                              tooltip: item['status'].toString().toUpperCase(),
                              onSelected: (action) {
                                if (action == 'deliver') {
                                  _confirmDelivered(item);
                                }
                                if (action == 'reverse') {
                                  _reverse(item);
                                }
                              },
                              itemBuilder: (_) => [
                                if (canConfirm)
                                  const PopupMenuItem(
                                    value: 'deliver',
                                    child: Text('Mark Arrived'),
                                  ),
                                if (canReverse)
                                  const PopupMenuItem(
                                    value: 'reverse',
                                    child: Text('Reverse'),
                                  ),
                                if (!canConfirm && !canReverse)
                                  PopupMenuItem(
                                    enabled: false,
                                    child: Text(
                                      item['status'].toString().toUpperCase(),
                                    ),
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
}

class DeliveryFormDialog extends StatefulWidget {
  const DeliveryFormDialog({
    super.key,
    required this.auth,
    this.initialScans = const [],
  });

  final AuthController auth;
  final List<ScannedProductIdentity> initialScans;

  @override
  State<DeliveryFormDialog> createState() => _DeliveryFormDialogState();
}

class _DeliveryFormDialogState extends State<DeliveryFormDialog> {
  final _driver = TextEditingController();
  final _notes = TextEditingController();
  final List<_DeliveryLineDraft> _lines = [];
  List<Map<String, dynamic>> _items = [];
  List<Map<String, dynamic>> _transportations = [];
  String? _salesOrderNumber;
  String? _transportationCode;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  Future<void> _scan() async {
    final scans = await scanProducts(context, widget.auth.api);
    if (scans == null || scans.isEmpty) return;
    await _applyScans(scans);
  }

  Future<void> _applyScans(List<ScannedProductIdentity> scans) async {
    if (_salesOrderNumber == null) {
      setState(
        () =>
            _error = 'Select the Sales Order before applying scanned products.',
      );
      return;
    }
    for (final scan in scans) {
      if (scan.lotId == null) {
        setState(
          () => _error =
              'Delivery requires a product QR that includes its Finished Good lot.',
        );
        return;
      }
      final item = _orderItems
          .where((item) => item['product_code'] == scan.productCode)
          .firstOrNull;
      if (item == null) {
        setState(
          () => _error =
              '${scan.productCode} is not an outstanding item on this Sales Order.',
        );
        return;
      }
      if (_lines.any(
        (line) =>
            line.item?['id'] == item['id'] && line.lot?['id'] == scan.lotId,
      )) {
        continue;
      }
      final line = _DeliveryLineDraft()..item = item;
      await _selectItem(line, item);
      final lot = line.lots
          .where((entry) => entry['id'] == scan.lotId)
          .firstOrNull;
      if (lot == null) {
        line.dispose();
        setState(
          () => _error =
              'Lot ${scan.lotNumber ?? scan.lotId} is not available as Finished Good stock.',
        );
        return;
      }
      line.lot = lot;
      line.quantityController.text = scan.availableQuantity?.toString() ?? '';
      if (mounted) setState(() => _lines.add(line));
    }
  }

  @override
  void initState() {
    super.initState();
    _loadItems();
  }

  @override
  void dispose() {
    _driver.dispose();
    _notes.dispose();
    for (final line in _lines) {
      line.dispose();
    }
    super.dispose();
  }

  List<String> get _orders =>
      _items
          .map((item) => item['sales_order_number'].toString())
          .toSet()
          .toList()
        ..sort();
  List<Map<String, dynamic>> get _orderItems => _items
      .where((item) => item['sales_order_number'] == _salesOrderNumber)
      .toList();

  Future<void> _loadItems() async {
    try {
      final responses = await Future.wait([
        widget.auth.api.getJson('/delivery/lookup/sales-order-items'),
        widget.auth.api.getJson(
          '/master-data/transportations?size=100&active_only=true',
        ),
      ]);
      if (mounted) {
        setState(() {
          _items = (responses[0] as List).cast<Map<String, dynamic>>();
          _transportations = (responses[1]['items'] as List)
              .cast<Map<String, dynamic>>();
        });
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _selectOrder(String? value) {
    for (final line in _lines) {
      line.dispose();
    }
    setState(() {
      _salesOrderNumber = value;
      _lines.clear();
    });
    if (value != null && widget.initialScans.isNotEmpty) {
      _applyScans(widget.initialScans);
    }
  }

  Future<void> _selectItem(
    _DeliveryLineDraft line,
    Map<String, dynamic>? item,
  ) async {
    setState(() {
      line.item = item;
      line.lot = null;
      line.lots = [];
    });
    if (item == null) return;
    try {
      final response = await widget.auth.api.getJson(
        '/delivery/lookup/finish-good-lots?product_code=${Uri.encodeQueryComponent(item['product_code'].toString())}&unit=${Uri.encodeQueryComponent(item['unit'].toString())}',
      );
      if (mounted) {
        setState(
          () => line.lots = (response as List).cast<Map<String, dynamic>>(),
        );
      }
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    }
  }

  Future<void> _save() async {
    final pairs = _lines
        .map((line) => '${line.item?['id']}:${line.lot?['id']}')
        .toSet();
    if (_salesOrderNumber == null ||
        _lines.isEmpty ||
        _driver.text.trim().isEmpty ||
        _lines.any((line) => !line.isComplete) ||
        pairs.length != _lines.length) {
      setState(
        () => _error =
            'Select one Sales Order and complete each unique product, lot, and quantity.',
      );
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.auth.api.postJson('/delivery/batch', {
        'delivery_date': DateTime.now().toIso8601String().substring(0, 10),
        'transportation_code': _transportationCode,
        'driver_name': _driver.text.trim(),
        'notes': _notes.text.trim(),
        'lines': _lines
            .map(
              (line) => {
                'sales_order_item_id': line.item!['id'],
                'lot_id': line.lot!['id'],
                'quantity': line.quantity,
              },
            )
            .toList(),
      });
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (exception) {
      if (mounted) setState(() => _error = exception.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Post Delivery'),
    content: SizedBox(
      width: 720,
      child: _loading
          ? const SizedBox(
              height: 120,
              child: Center(child: CircularProgressIndicator()),
            )
          : SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: _salesOrderNumber,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Sales Order *',
                    ),
                    items: _orders
                        .map(
                          (number) => DropdownMenuItem(
                            value: number,
                            child: Text(number),
                          ),
                        )
                        .toList(),
                    onChanged: _selectOrder,
                  ),
                  if (supportsMobileProductScanner)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: OutlinedButton.icon(
                          onPressed: _salesOrderNumber == null ? null : _scan,
                          icon: const Icon(Icons.qr_code_scanner),
                          label: const Text('Scan Finished Good Lots'),
                        ),
                      ),
                    ),
                  const SizedBox(height: 14),
                  ..._lines.asMap().entries.map(
                    (entry) => _DeliveryLineEditor(
                      key: ValueKey(entry.value),
                      line: entry.value,
                      items: _orderItems,
                      onItemChanged: (item) => _selectItem(entry.value, item),
                      onChanged: () => setState(() {}),
                      onRemove: () => setState(() {
                        entry.value.dispose();
                        _lines.removeAt(entry.key);
                      }),
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: OutlinedButton.icon(
                      onPressed: _salesOrderNumber == null
                          ? null
                          : () => setState(
                              () => _lines.add(_DeliveryLineDraft()),
                            ),
                      icon: const Icon(Icons.add),
                      label: const Text('Add Product / Lot'),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _driver,
                    decoration: const InputDecoration(
                      labelText: 'Driver Name *',
                    ),
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<String>(
                    initialValue: _transportationCode,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Transportation',
                    ),
                    items: _transportations
                        .map(
                          (item) => DropdownMenuItem(
                            value: item['code'].toString(),
                            child: Text(
                              '${item['vehicle_number']} — ${item['vehicle_type']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) =>
                        setState(() => _transportationCode = value),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _notes,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Notes'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 14),
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  ],
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
        child: Text(_saving ? 'Posting...' : 'Post Delivery'),
      ),
    ],
  );
}

class _DeliveryLineDraft {
  Map<String, dynamic>? item;
  Map<String, dynamic>? lot;
  List<Map<String, dynamic>> lots = [];
  final quantityController = TextEditingController();
  num? get quantity =>
      num.tryParse(quantityController.text.trim().replaceAll(',', '.'));
  bool get isComplete =>
      item != null && lot != null && quantity != null && quantity! > 0;
  void dispose() => quantityController.dispose();
}

class _DeliveryLineEditor extends StatelessWidget {
  const _DeliveryLineEditor({
    super.key,
    required this.line,
    required this.items,
    required this.onItemChanged,
    required this.onChanged,
    required this.onRemove,
  });
  final _DeliveryLineDraft line;
  final List<Map<String, dynamic>> items;
  final ValueChanged<Map<String, dynamic>?> onItemChanged;
  final VoidCallback onChanged;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 10),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Delivery Line',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              IconButton(
                onPressed: onRemove,
                icon: const Icon(Icons.delete_outline),
              ),
            ],
          ),
          DropdownButtonFormField<Map<String, dynamic>>(
            initialValue: line.item,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Outstanding Product *',
            ),
            items: items
                .map(
                  (item) => DropdownMenuItem(
                    value: item,
                    child: Text(
                      '${item['product_code']} — ${formatQuantity(item['outstanding_quantity'], item['unit'].toString())} ${unitLabel(item['unit'].toString())}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: onItemChanged,
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<Map<String, dynamic>>(
            initialValue: line.lot,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Finished Goods Lot *',
            ),
            items: line.lots
                .map(
                  (lot) => DropdownMenuItem(
                    value: lot,
                    child: Text(
                      'Lot ${lot['lot_number']} — ${formatQuantity(lot['quantity'], lot['unit'].toString())} ${unitLabel(lot['unit'].toString())}',
                    ),
                  ),
                )
                .toList(),
            onChanged: line.lots.isEmpty
                ? null
                : (lot) {
                    line.lot = lot;
                    onChanged();
                  },
          ),
          const SizedBox(height: 10),
          TextField(
            controller: line.quantityController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            onChanged: (_) => onChanged(),
            decoration: InputDecoration(
              labelText: 'Delivery Quantity *',
              helperText: line.item == null
                  ? null
                  : 'Outstanding: ${formatQuantity(line.item!['outstanding_quantity'], line.item!['unit'].toString())} ${unitLabel(line.item!['unit'].toString())}',
            ),
          ),
        ],
      ),
    ),
  );
}
