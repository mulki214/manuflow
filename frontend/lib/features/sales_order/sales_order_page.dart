import 'package:flutter/material.dart';
import 'package:file_saver/file_saver.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../core/api_client.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../../shared/module_navigation.dart';
import '../../shared/units.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../purchasing/purchasing_page.dart';
import '../users/change_password_dialog.dart';
import 'sales_order_form_dialog.dart';
import 'sales_order_models.dart';
import '../receiving/receiving_page.dart';
import '../warehouse/warehouse_page.dart';
import '../production/production_page.dart';
import '../quality/quality_page.dart';

class SalesOrderPage extends StatefulWidget {
  const SalesOrderPage({super.key, required this.auth});
  final AuthController auth;

  @override
  State<SalesOrderPage> createState() => _SalesOrderPageState();
}

class _SalesOrderPageState extends State<SalesOrderPage> {
  final _search = TextEditingController();
  List<SalesOrderModel> _orders = [];
  bool _checkingAccess = true;
  bool _allowed = false;
  bool _loading = false;
  String? _error;
  String? _statusFilter;
  bool _outstandingOnly = false;
  int _outstandingOrder = 0;
  Map<String, dynamic> _totalMaterial = {};
  Map<String, dynamic> _outstandingMaterial = {};
  int _page = 1;
  final int _size = 10;
  int _total = 0;

  int get _totalPages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _verifyAccess();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _verifyAccess() async {
    try {
      final access = await widget.auth.refreshSalesOrderAccess();
      if (!mounted) return;
      setState(() => _allowed = access.canAccess);
      if (access.canAccess) await _load();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
        return;
      }
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to verify Sales Order access.');
      }
    } finally {
      if (mounted) setState(() => _checkingAccess = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final term = _search.text.trim();
    final query = [
      'page=$_page',
      'size=$_size',
      if (term.isNotEmpty) 'search=${Uri.encodeQueryComponent(term)}',
      if (_statusFilter != null) 'status=$_statusFilter',
      if (_outstandingOnly) 'outstanding_only=true',
    ].join('&');
    try {
      final response = await widget.auth.api.getJson('/sales-orders?$query');
      if (!mounted) return;
      setState(() {
        _orders = (response['items'] as List)
            .map(
              (item) => SalesOrderModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
        _outstandingOrder = response['outstanding_order'] as int? ?? 0;
        _totalMaterial = Map<String, dynamic>.from(
          response['total_material_by_unit'] as Map? ?? const {},
        );
        _outstandingMaterial = Map<String, dynamic>.from(
          response['outstanding_material_by_unit'] as Map? ?? const {},
        );
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
        return;
      }
      if (exception.statusCode == 403) {
        if (mounted) setState(() => _allowed = false);
        return;
      }
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Unable to load Sales Orders.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([SalesOrderModel? order]) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => SalesOrderFormDialog(api: widget.auth.api, order: order),
    );
    if (changed == true) {
      await _load();
      _message(
        order == null
            ? 'Sales Order created and waiting for review.'
            : 'Sales Order updated.',
      );
    }
  }

  Future<void> _delete(SalesOrderModel order) async {
    final confirmed = await showDeleteConfirmation(
      context,
      title: 'Delete Sales Order?',
      message:
          'Delete ${order.salesOrderNumber}? This action cannot be undone.',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.delete('/sales-orders/${order.salesOrderNumber}');
      if (_orders.length == 1 && _page > 1) _page--;
      await _load();
      _message('Sales Order deleted.');
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  Future<void> _downloadPdf(SalesOrderModel order) async {
    try {
      final bytes = await widget.auth.api.getBytes(
        '/sales-orders/${Uri.encodeComponent(order.salesOrderNumber)}/pdf',
      );
      await FileSaver.instance.saveFile(
        name: 'sales-order-${order.salesOrderNumber.replaceAll('/', '-')}',
        bytes: bytes,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  Future<void> _approve(SalesOrderModel order) async {
    final confirmed = await _confirm(
      'Approve Sales Order?',
      'Approve ${order.salesOrderNumber}? It will become read-only.',
      'Approve',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.postJson(
        '/sales-orders/${order.salesOrderNumber}/approve',
        {},
      );
      await _load();
      _message('Sales Order approved.');
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  Future<void> _reject(SalesOrderModel order) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject Sales Order?'),
        content: TextField(
          controller: controller,
          autofocus: true,
          minLines: 3,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Rejection Reason',
            helperText: 'Minimum 3 characters',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.length >= 3) Navigator.pop(context, value);
            },
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null) return;
    try {
      await widget.auth.api.postJson(
        '/sales-orders/${order.salesOrderNumber}/reject',
        {'reason': reason},
      );
      await _load();
      _message('Sales Order rejected.');
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  Future<bool> _confirm(String title, String message, String action) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(action),
            ),
          ],
        ),
      ) ??
      false;

  void _message(String value) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(value)));
    }
  }

  Future<void> _changePassword() async => showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (_) => ChangePasswordDialog(api: widget.auth.api),
  );

  void _selectModule(AppModule module) {
    if (module == AppModule.user) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    } else if (module == AppModule.masterData) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => MasterDataPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.purchasing &&
        widget.auth.canAccessPurchasing) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => PurchasingPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.receiving &&
        widget.auth.canAccessReceiving) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ReceivingPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.warehouse &&
        widget.auth.canAccessWarehouse) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => WarehousePage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.production &&
        widget.auth.canAccessProduction) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => ProductionPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.quality && widget.auth.canAccessQuality) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => QualityPage(auth: widget.auth)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checkingAccess) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_allowed) return _accessDenied();
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(
              title: const Text(
                'Sales Order',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              actions: [
                IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
                IconButton(
                  onPressed: widget.auth.logout,
                  icon: const Icon(Icons.logout),
                ),
              ],
            ),
            drawer: _SalesOrderDrawer(
              auth: widget.auth,
              onSelected: _selectModule,
            ),
            body: _content(desktop),
            floatingActionButton: FloatingActionButton.extended(
              onPressed: _openForm,
              icon: const Icon(Icons.add),
              label: const Text('Create SO'),
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.salesOrder,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.salesOrder,
                ),
                onChangePassword: _changePassword,
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Sales Order')),
                  body: _content(desktop),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _accessDenied() => Scaffold(
    appBar: AppBar(title: const Text('Sales Order')),
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.lock_outline, size: 64, color: Color(0xFFB42318)),
          const SizedBox(height: 16),
          Text(
            'Access Denied',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            _error ??
                'Only the PIC or Head of the Sales Department can access this module.',
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: () =>
                Navigator.of(context).popUntil((route) => route.isFirst),
            child: const Text('Back to User'),
          ),
        ],
      ),
    ),
  );

  Widget _content(bool desktop) => SafeArea(
    child: Padding(
      padding: EdgeInsets.all(desktop ? 32 : 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Sales Orders',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '$_total Sales Orders • quantities follow each selected unit',
                      style: const TextStyle(color: Color(0xFF667085)),
                    ),
                  ],
                ),
              ),
              if (desktop)
                FilledButton.icon(
                  onPressed: _openForm,
                  icon: const Icon(Icons.add),
                  label: const Text('Create SO'),
                ),
            ],
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              _summaryCard('Total Orders', '$_total', desktop),
              _summaryCard('Outstanding Orders', '$_outstandingOrder', desktop),
              _summaryCard('Total Material', _unitMap(_totalMaterial), desktop),
              _summaryCard(
                'Outstanding Material',
                _unitMap(_outstandingMaterial),
                desktop,
              ),
            ],
          ),
          const SizedBox(height: 14),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  SizedBox(
                    width: desktop ? 420 : double.infinity,
                    child: TextField(
                      controller: _search,
                      onSubmitted: (_) {
                        _page = 1;
                        _load();
                      },
                      decoration: const InputDecoration(
                        hintText: 'Search SO, customer PO, or customer...',
                        prefixIcon: Icon(Icons.search),
                        isDense: true,
                      ),
                    ),
                  ),
                  FilterChip(
                    label: const Text('Outstanding Orders'),
                    selected: _outstandingOnly,
                    onSelected: (value) {
                      setState(() {
                        _outstandingOnly = value;
                        _page = 1;
                      });
                      _load();
                    },
                  ),
                  SizedBox(
                    width: 180,
                    child: DropdownButtonFormField<String?>(
                      initialValue: _statusFilter,
                      decoration: const InputDecoration(
                        labelText: 'Status',
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: null,
                          child: Text('All Statuses'),
                        ),
                        DropdownMenuItem(
                          value: 'waiting_review',
                          child: Text('Waiting Review'),
                        ),
                        DropdownMenuItem(
                          value: 'approved',
                          child: Text('Approved'),
                        ),
                        DropdownMenuItem(
                          value: 'rejected',
                          child: Text('Rejected'),
                        ),
                      ],
                      onChanged: (value) {
                        _statusFilter = value;
                        _page = 1;
                        _load();
                      },
                    ),
                  ),
                  IconButton.filledTonal(
                    onPressed: _load,
                    icon: const Icon(Icons.search),
                  ),
                  IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Expanded(child: _body(desktop)),
          if (!_loading && _error == null)
            CrudPaginationBar(
              currentPage: _page,
              totalPages: _totalPages,
              totalRecords: _total,
              onPrevious: _page > 1
                  ? () {
                      _page--;
                      _load();
                    }
                  : null,
              onNext: _page < _totalPages
                  ? () {
                      _page++;
                      _load();
                    }
                  : null,
            ),
        ],
      ),
    ),
  );

  Widget _body(bool desktop) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text(_error!));
    if (_orders.isEmpty) {
      return const Center(child: Text('No Sales Orders found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() => Card(
    clipBehavior: Clip.antiAlias,
    child: SingleChildScrollView(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          showCheckboxColumn: false,
          headingRowColor: WidgetStateProperty.all(const Color(0xFFF9FAFB)),
          columns: const [
            DataColumn(label: Text('SO NUMBER')),
            DataColumn(label: Text('PO RECEIPT')),
            DataColumn(label: Text('CUSTOMER PO DATE / NO')),
            DataColumn(label: Text('CUSTOMER')),
            DataColumn(label: Text('DESCRIPTION')),
            DataColumn(label: Text('QUANTITY')),
            DataColumn(label: Text('TOTAL (IDR)')),
            DataColumn(label: Text('ORDER TYPE')),
            DataColumn(label: Text('DELIVERY')),
            DataColumn(label: Text('STATUS')),
            DataColumn(label: Text('FULFILLMENT')),
            DataColumn(label: Text('ACTIONS')),
          ],
          rows: _orders
              .map(
                (order) => DataRow(
                  onSelectChanged: (_) => _openDetail(order),
                  cells: [
                    DataCell(
                      Text(
                        order.salesOrderNumber,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    DataCell(Text(_formatDate(order.poReceiptDate))),
                    DataCell(
                      Text(
                        '${_formatDate(order.customerPoDate)}\n${order.customerPoNumber}',
                      ),
                    ),
                    DataCell(
                      Text('${order.customerCode}\n${order.customerName}'),
                    ),
                    DataCell(
                      SizedBox(
                        width: 220,
                        child: Text(
                          order.descriptions,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    DataCell(Text(order.quantitySummary)),
                    DataCell(Text(_formatNumber(order.grandTotal))),
                    DataCell(Text(salesOrderTypeLabel(order.orderType))),
                    DataCell(Text(_formatDate(order.deliveryDate))),
                    DataCell(_status(order.status)),
                    DataCell(_fulfillmentChip(order.fulfillmentStatus)),
                    DataCell(_actions(order)),
                  ],
                ),
              )
              .toList(),
        ),
      ),
    ),
  );

  Widget _cards() => ListView.separated(
    padding: const EdgeInsets.only(bottom: 88),
    itemCount: _orders.length,
    separatorBuilder: (_, _) => const SizedBox(height: 10),
    itemBuilder: (context, index) {
      final order = _orders[index];
      return Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => _openDetail(order),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        order.salesOrderNumber,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ),
                    _status(order.status),
                    const SizedBox(width: 6),
                    _fulfillmentChip(order.fulfillmentStatus),
                  ],
                ),
                const SizedBox(height: 10),
                Text('${order.customerCode} — ${order.customerName}'),
                Text(
                  'Customer PO ${order.customerPoNumber}',
                  style: const TextStyle(color: Color(0xFF667085)),
                ),
                const Divider(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${order.items.length} item • ${order.quantitySummary}',
                      ),
                    ),
                    _actions(order),
                  ],
                ),
              ],
            ),
          ),
        ),
      );
    },
  );

  Widget _actions(SalesOrderModel order) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      if (order.canReview) ...[
        IconButton(
          onPressed: () => _approve(order),
          icon: const Icon(Icons.check_circle_outline),
          color: const Color(0xFF067647),
        ),
        IconButton(
          onPressed: () => _reject(order),
          icon: const Icon(Icons.cancel_outlined),
          color: const Color(0xFFB42318),
        ),
      ],
      IconButton(
        onPressed: order.canEdit ? () => _openForm(order) : null,
        icon: const Icon(Icons.edit_outlined),
      ),
      IconButton(
        onPressed: order.canDelete ? () => _delete(order) : null,
        icon: const Icon(Icons.delete_outline),
      ),
    ],
  );

  Widget _status(String value) {
    final color = switch (value) {
      'approved' => const Color(0xFF067647),
      'rejected' => const Color(0xFFB42318),
      _ => const Color(0xFFB54708),
    };
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(salesOrderStatusLabel(value)),
      labelStyle: TextStyle(color: color, fontSize: 12),
      backgroundColor: color.withValues(alpha: 0.08),
    );
  }

  Widget _fulfillmentChip(String value) {
    final closed = value == 'closed';
    final color = closed ? const Color(0xFF475467) : const Color(0xFF175CD3);
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(closed ? 'Closed' : 'Open'),
      labelStyle: TextStyle(color: color, fontSize: 12),
      backgroundColor: color.withValues(alpha: 0.08),
      side: BorderSide(color: color.withValues(alpha: 0.25)),
    );
  }

  void _openDetail(SalesOrderModel order) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Expanded(child: Text(order.salesOrderNumber)),
            _status(order.status),
            const SizedBox(width: 6),
            _fulfillmentChip(order.fulfillmentStatus),
          ],
        ),
        content: SizedBox(
          width: 850,
          height: 650,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Wrap(
                  spacing: 24,
                  runSpacing: 14,
                  children: [
                    _detail(
                      'PO Receipt Date',
                      _formatDate(order.poReceiptDate),
                    ),
                    _detail(
                      'Customer PO',
                      '${order.customerPoNumber} • ${_formatDate(order.customerPoDate)}',
                    ),
                    _detail(
                      'Customer',
                      '${order.customerCode} — ${order.customerName}',
                    ),
                    _detail('Order Type', salesOrderTypeLabel(order.orderType)),
                    _detail(
                      'Fulfillment',
                      order.fulfillmentStatus == 'closed'
                          ? 'Closed — all items delivered'
                          : 'Open — awaiting delivery',
                    ),
                    _detail('Delivery Date', _formatDate(order.deliveryDate)),
                    _detail('Created By', order.createdByName),
                    _detail(
                      'Bill To',
                      '${order.billToAddress}\n${order.billToPhone}',
                    ),
                    _detail(
                      'Ship To',
                      '${order.shipToName}\n${order.shipToAddress}\n${order.shipToContactPerson} • ${order.shipToPhone}',
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Text('Items', style: Theme.of(context).textTheme.titleMedium),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    columns: const [
                      DataColumn(label: Text('NO')),
                      DataColumn(label: Text('DESCRIPTION')),
                      DataColumn(label: Text('PART NO')),
                      DataColumn(label: Text('ORDERED')),
                      DataColumn(label: Text('UNIT')),
                      DataColumn(label: Text('MATERIAL RECEIVED')),
                      DataColumn(label: Text('OUTSTANDING MATERIAL')),
                      DataColumn(label: Text('DELIVERED')),
                      DataColumn(label: Text('OUTSTANDING ORDER')),
                      DataColumn(label: Text('OUTSTANDING NOTE')),
                      DataColumn(label: Text('AMOUNT')),
                    ],
                    rows: order.items.indexed
                        .map(
                          (entry) => DataRow(
                            cells: [
                              DataCell(Text('${entry.$1 + 1}')),
                              DataCell(
                                SizedBox(
                                  width: 220,
                                  child: Text(entry.$2.description),
                                ),
                              ),
                              DataCell(Text(entry.$2.partNo)),
                              DataCell(
                                Text(_formatNumber(entry.$2.quantityGrams)),
                              ),
                              DataCell(Text(unitLabel(entry.$2.unit))),
                              DataCell(
                                Text(
                                  _formatNumber(
                                    entry.$2.materialReceivedQuantity,
                                  ),
                                ),
                              ),
                              DataCell(
                                Text(
                                  _formatNumber(
                                    entry.$2.outstandingMaterialQuantity,
                                  ),
                                ),
                              ),
                              DataCell(
                                Text(_formatNumber(entry.$2.deliveredQuantity)),
                              ),
                              DataCell(
                                Text(
                                  _formatNumber(
                                    entry.$2.outstandingOrderQuantity,
                                  ),
                                ),
                              ),
                              DataCell(
                                Text(
                                  entry.$2.outstandingNote.isEmpty
                                      ? '-'
                                      : entry.$2.outstandingNote,
                                ),
                              ),
                              DataCell(
                                Text('IDR ${_formatNumber(entry.$2.amount)}'),
                              ),
                            ],
                          ),
                        )
                        .toList(),
                  ),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    'Grand Total: IDR ${_formatNumber(order.grandTotal)}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  'Operational Progress',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                ...order.items.map(
                  (item) => Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(
                        '${item.productCode}: Warehouse ${_formatNumber(item.materialReceivedQuantity)} ${unitLabel(item.unit)} • '
                        'WIP ${_formatNumber(item.wipQuantity)} • Finish Goods ${_formatNumber(item.finishGoodQuantity)} • '
                        'Sent ${_formatNumber(item.dispatchedQuantity)} • Delivered ${_formatNumber(item.deliveredQuantity)}',
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Wrap(
                  spacing: 28,
                  runSpacing: 14,
                  children: [
                    _qrSignature(
                      'Created By',
                      order.createdByName,
                      order.creatorQrPayload,
                    ),
                    if (order.approvalQrPayload != null)
                      _qrSignature(
                        'Approved By',
                        order.reviewedByName ?? '-',
                        order.approvalQrPayload!,
                      ),
                  ],
                ),
                if (order.notes.isNotEmpty) _detail('Notes', order.notes),
                if (order.rejectionReason != null)
                  _detail('Rejection Reason', order.rejectionReason!),
              ],
            ),
          ),
        ),
        actions: [
          OutlinedButton.icon(
            onPressed: () => _downloadPdf(order),
            icon: const Icon(Icons.picture_as_pdf_outlined),
            label: const Text('Download PDF'),
          ),
          if (order.canEdit)
            OutlinedButton.icon(
              onPressed: () {
                Navigator.pop(context);
                _openForm(order);
              },
              icon: const Icon(Icons.edit),
              label: const Text('Edit'),
            ),
          if (order.canReview)
            FilledButton.icon(
              onPressed: () {
                Navigator.pop(context);
                _approve(order);
              },
              icon: const Icon(Icons.check),
              label: const Text('Approve'),
            ),
        ],
      ),
    );
  }

  Widget _detail(String label, String value) => SizedBox(
    width: 280,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: Color(0xFF667085), fontSize: 12),
        ),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
    ),
  );

  Widget _summaryCard(String label, String value, bool desktop) => SizedBox(
    width: desktop ? 220 : 180,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(color: Color(0xFF667085))),
            const SizedBox(height: 6),
            Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
          ],
        ),
      ),
    ),
  );

  Widget _qrSignature(String label, String name, String payload) => SizedBox(
    width: 150,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF667085))),
        const SizedBox(height: 6),
        QrImageView(data: payload, size: 96),
        Text(name, style: const TextStyle(fontWeight: FontWeight.w700)),
      ],
    ),
  );

  String _unitMap(Map<String, dynamic> values) => values.isEmpty
      ? '0'
      : values.entries
            .map(
              (entry) =>
                  '${_formatNumber(double.parse(entry.value.toString()))} ${entry.key}',
            )
            .join(' • ');

  String _formatDate(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';

  String _formatNumber(double value) =>
      value.toStringAsFixed(value.truncateToDouble() == value ? 0 : 2);
}

class _SalesOrderDrawer extends StatelessWidget {
  const _SalesOrderDrawer({required this.auth, required this.onSelected});

  final AuthController auth;
  final ValueChanged<AppModule> onSelected;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            UserAccountsDrawerHeader(
              currentAccountPicture: CircleAvatar(
                child: Text(auth.currentUser?.initials ?? 'U'),
              ),
              accountName: Text(auth.currentUser?.fullName ?? ''),
              accountEmail: Text(auth.currentUser?.email ?? ''),
            ),
            Expanded(
              child: ListView(
                children: AppModule.values
                    .where(
                      (module) => switch (module) {
                        AppModule.purchasing => auth.canAccessPurchasing,
                        AppModule.salesOrder => auth.canAccessSalesOrder,
                        AppModule.receiving => auth.canAccessReceiving,
                        AppModule.warehouse => auth.canAccessWarehouse,
                        AppModule.production => auth.canAccessProduction,
                        _ => true,
                      },
                    )
                    .map(
                      (module) => ListTile(
                        selected: module == AppModule.salesOrder,
                        leading: Icon(module.icon),
                        title: Text(module.label),
                        onTap: () {
                          Navigator.pop(context);
                          if (module != AppModule.salesOrder) {
                            onSelected(module);
                          }
                        },
                      ),
                    )
                    .toList(),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Keluar'),
              onTap: auth.logout,
            ),
          ],
        ),
      ),
    );
  }
}
