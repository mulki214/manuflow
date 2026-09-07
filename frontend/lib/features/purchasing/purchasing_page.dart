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
import '../users/change_password_dialog.dart';
import 'purchase_order_form_dialog.dart';
import 'purchase_order_models.dart';
import '../sales_order/sales_order_page.dart';
import '../receiving/receiving_page.dart';
import '../warehouse/warehouse_page.dart';
import '../production/production_page.dart';
import '../quality/quality_page.dart';

class PurchasingPage extends StatefulWidget {
  const PurchasingPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<PurchasingPage> createState() => _PurchasingPageState();
}

class _PurchasingPageState extends State<PurchasingPage> {
  final _search = TextEditingController();
  List<PurchaseOrderModel> _orders = [];
  bool _checkingAccess = true;
  bool _allowed = false;
  bool _loading = false;
  String? _error;
  String? _statusFilter;
  String? _fulfillmentFilter;
  DateTime? _dateFrom;
  DateTime? _dateTo;
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
      final access = await widget.auth.refreshPurchasingAccess();
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
      if (mounted) setState(() => _error = 'Unable to verify module access.');
    } finally {
      if (mounted) setState(() => _checkingAccess = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final search = _search.text.trim();
    final query = [
      'page=$_page',
      'size=$_size',
      if (search.isNotEmpty) 'search=${Uri.encodeQueryComponent(search)}',
      if (_statusFilter != null) 'status=$_statusFilter',
      if (_fulfillmentFilter != null) 'fulfillment_status=$_fulfillmentFilter',
      if (_dateFrom != null) 'date_from=${_apiDate(_dateFrom!)}',
      if (_dateTo != null) 'date_to=${_apiDate(_dateTo!)}',
    ].join('&');
    try {
      final response = await widget.auth.api.getJson('/purchasing?$query');
      if (!mounted) return;
      setState(() {
        _orders = (response['items'] as List)
            .map(
              (item) =>
                  PurchaseOrderModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
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
      if (mounted) setState(() => _error = 'Unable to load Purchase Orders.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([PurchaseOrderModel? order]) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          PurchaseOrderFormDialog(api: widget.auth.api, order: order),
    );
    if (changed == true) {
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              order == null
                  ? 'Purchase Order created and waiting for review.'
                  : 'Purchase Order updated.',
            ),
          ),
        );
      }
    }
  }

  Future<void> _downloadPdf(PurchaseOrderModel order) async {
    try {
      final bytes = await widget.auth.api.getBytes(
        '/purchasing/${Uri.encodeComponent(order.poNumber)}/pdf',
      );
      await FileSaver.instance.saveFile(
        name: 'purchase-order-${order.poNumber.replaceAll('/', '-')}',
        bytes: bytes,
        fileExtension: 'pdf',
        mimeType: MimeType.pdf,
      );
    } on ApiException catch (exception) {
      _showError(exception.message);
    }
  }

  Future<void> _delete(PurchaseOrderModel order) async {
    final confirmed = await showDeleteConfirmation(
      context,
      title: 'Delete Purchase Order?',
      message:
          'Delete ${order.poNumber}? Only a Purchase Order waiting for review can be deleted.',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.delete('/purchasing/${order.poNumber}');
      if (_orders.length == 1 && _page > 1) _page--;
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchase Order deleted.')),
        );
      }
    } on ApiException catch (exception) {
      _showError(exception.message);
    }
  }

  Future<void> _approve(PurchaseOrderModel order) async {
    final confirmed = await _confirmation(
      title: 'Approve Purchase Order?',
      message: 'Approve ${order.poNumber}? It will become read-only.',
      action: 'Approve',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.postJson(
        '/purchasing/${order.poNumber}/approve',
        {},
      );
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchase Order approved.')),
        );
      }
    } on ApiException catch (exception) {
      _showError(exception.message);
    }
  }

  Future<void> _reject(PurchaseOrderModel order) async {
    final reason = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject Purchase Order?'),
        content: TextField(
          controller: reason,
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
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () {
              final value = reason.text.trim();
              if (value.length >= 3) Navigator.pop(context, value);
            },
            child: const Text('Reject'),
          ),
        ],
      ),
    );
    reason.dispose();
    if (result == null) return;
    try {
      await widget.auth.api.postJson('/purchasing/${order.poNumber}/reject', {
        'reason': result,
      });
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Purchase Order rejected.')),
        );
      }
    } on ApiException catch (exception) {
      _showError(exception.message);
    }
  }

  Future<bool> _confirmation({
    required String title,
    required String message,
    required String action,
  }) async {
    return await showDialog<bool>(
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
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _changePassword() async {
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ChangePasswordDialog(api: widget.auth.api),
    );
  }

  void _selectModule(AppModule module) {
    if (module == AppModule.user) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    } else if (module == AppModule.masterData) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => MasterDataPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.salesOrder &&
        widget.auth.canAccessSalesOrder) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => SalesOrderPage(auth: widget.auth),
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
                'Purchasing',
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
            drawer: _PurchasingDrawer(
              auth: widget.auth,
              onSelected: _selectModule,
            ),
            body: _content(desktop),
            floatingActionButton: FloatingActionButton.extended(
              onPressed: _openForm,
              icon: const Icon(Icons.add),
              label: const Text('Create PO'),
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.purchasing,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.purchasing,
                ),
                onChangePassword: _changePassword,
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Purchasing')),
                  body: _content(desktop),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _accessDenied() {
    return Scaffold(
      appBar: AppBar(title: const Text('Purchasing')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.lock_outline,
                size: 64,
                color: Color(0xFFB42318),
              ),
              const SizedBox(height: 16),
              Text(
                'Access Denied',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                _error ??
                    'Only the PIC or Head of the Purchasing Department can access this module.',
                textAlign: TextAlign.center,
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
      ),
    );
  }

  Widget _content(bool desktop) {
    return SafeArea(
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
                        'Purchase Orders',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '$_total PO • quantities follow each selected unit',
                        style: const TextStyle(color: Color(0xFF667085)),
                      ),
                    ],
                  ),
                ),
                if (desktop)
                  FilledButton.icon(
                    onPressed: _openForm,
                    icon: const Icon(Icons.add),
                    label: const Text('Create PO'),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    SizedBox(
                      width: desktop ? 420 : 260,
                      child: TextField(
                        controller: _search,
                        onSubmitted: (_) {
                          _page = 1;
                          _load();
                        },
                        decoration: const InputDecoration(
                          hintText: 'Search PO number or supplier...',
                          prefixIcon: Icon(Icons.search),
                          isDense: true,
                        ),
                      ),
                    ),
                    OutlinedButton.icon(
                      onPressed: () async {
                        final range = await showDateRangePicker(
                          context: context,
                          firstDate: DateTime(2020),
                          lastDate: DateTime(2200),
                          initialDateRange: _dateFrom != null && _dateTo != null
                              ? DateTimeRange(start: _dateFrom!, end: _dateTo!)
                              : null,
                        );
                        if (range != null) {
                          setState(() {
                            _dateFrom = range.start;
                            _dateTo = range.end;
                            _page = 1;
                          });
                          _load();
                        }
                      },
                      icon: const Icon(Icons.date_range_outlined),
                      label: Text(
                        _dateFrom == null
                            ? 'PO Date Range'
                            : '${_formatDate(_dateFrom!)} – ${_formatDate(_dateTo!)}',
                      ),
                    ),
                    if (_dateFrom != null)
                      IconButton(
                        tooltip: 'Clear Date Range',
                        onPressed: () {
                          setState(() {
                            _dateFrom = null;
                            _dateTo = null;
                            _page = 1;
                          });
                          _load();
                        },
                        icon: const Icon(Icons.event_busy_outlined),
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
                    SizedBox(
                      width: 180,
                      child: DropdownButtonFormField<String?>(
                        initialValue: _fulfillmentFilter,
                        decoration: const InputDecoration(
                          labelText: 'Fulfillment',
                          isDense: true,
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: null,
                            child: Text('All Fulfillment'),
                          ),
                          DropdownMenuItem(value: 'open', child: Text('Open')),
                          DropdownMenuItem(
                            value: 'closed',
                            child: Text('Closed'),
                          ),
                        ],
                        onChanged: (value) {
                          _fulfillmentFilter = value;
                          _page = 1;
                          _load();
                        },
                      ),
                    ),
                    IconButton.filledTonal(
                      onPressed: () {
                        _page = 1;
                        _load();
                      },
                      icon: const Icon(Icons.search),
                    ),
                    IconButton(
                      onPressed: _load,
                      icon: const Icon(Icons.refresh),
                    ),
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
  }

  Widget _body(bool desktop) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 48),
            const SizedBox(height: 12),
            Text(_error!),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: _load, child: const Text('Try Again')),
          ],
        ),
      );
    }
    if (_orders.isEmpty) {
      return const Center(child: Text('No Purchase Orders found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: ScrollableDataTable(
        child: DataTable(
          showCheckboxColumn: false,
          headingRowColor: WidgetStateProperty.all(const Color(0xFFF9FAFB)),
          columns: const [
            DataColumn(label: Text('PO DATE')),
            DataColumn(label: Text('PO NUMBER')),
            DataColumn(label: Text('SUPPLIER')),
            DataColumn(label: Text('PART NAME / NO')),
            DataColumn(label: Text('QUANTITY')),
            DataColumn(label: Text('TOTAL (IDR)')),
            DataColumn(label: Text('QUOTATION')),
            DataColumn(label: Text('REQUEST DELIVERY')),
            DataColumn(label: Text('STATUS')),
            DataColumn(label: Text('FULFILLMENT')),
            DataColumn(label: Text('ACTIONS')),
          ],
          rows: _orders
              .map(
                (order) => DataRow(
                  onSelectChanged: (_) => _openDetail(order),
                  cells: [
                    DataCell(Text(_formatDate(order.poDate))),
                    DataCell(
                      Text(
                        order.poNumber,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    DataCell(
                      Text('${order.supplierCode}\n${order.supplierName}'),
                    ),
                    DataCell(
                      SizedBox(
                        width: 210,
                        child: Text(
                          '${order.partNames}\n${order.partNumbers}',
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    DataCell(Text(order.quantitySummary)),
                    DataCell(Text(_formatNumber(order.grandTotal))),
                    DataCell(
                      Text(
                        '${order.quotationReference ?? '-'}\n${order.quotationDate == null ? '-' : _formatDate(order.quotationDate!)}',
                      ),
                    ),
                    DataCell(Text(_formatDate(order.requestedDeliveryDate))),
                    DataCell(_statusChip(order.status)),
                    DataCell(_fulfillmentChip(order.fulfillmentStatus)),
                    DataCell(_actions(order)),
                  ],
                ),
              )
              .toList(),
        ),
      ),
    );
  }

  Widget _cards() {
    return ListView.separated(
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
                          order.poNumber,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ),
                      _statusChip(order.status),
                      const SizedBox(width: 6),
                      _fulfillmentChip(order.fulfillmentStatus),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text('${order.supplierCode} — ${order.supplierName}'),
                  const SizedBox(height: 4),
                  Text(
                    '${order.items.length} item • ${order.quantitySummary} • IDR ${_formatNumber(order.grandTotal)}',
                    style: const TextStyle(color: Color(0xFF667085)),
                  ),
                  const Divider(height: 24),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Delivery ${_formatDate(order.requestedDeliveryDate)}',
                          style: const TextStyle(fontSize: 13),
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
  }

  Widget _actions(PurchaseOrderModel order) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (order.canReview) ...[
          IconButton(
            tooltip: 'Approve',
            onPressed: () => _approve(order),
            icon: const Icon(Icons.check_circle_outline),
            color: const Color(0xFF067647),
          ),
          IconButton(
            tooltip: 'Reject',
            onPressed: () => _reject(order),
            icon: const Icon(Icons.cancel_outlined),
            color: const Color(0xFFB42318),
          ),
        ],
        IconButton(
          tooltip: 'Edit',
          onPressed: order.canEdit ? () => _openForm(order) : null,
          icon: const Icon(Icons.edit_outlined),
        ),
        IconButton(
          tooltip: 'Delete',
          onPressed: order.canDelete ? () => _delete(order) : null,
          icon: const Icon(Icons.delete_outline),
          color: Theme.of(context).colorScheme.error,
        ),
      ],
    );
  }

  Widget _statusChip(String status) {
    final color = switch (status) {
      'approved' => const Color(0xFF067647),
      'rejected' => const Color(0xFFB42318),
      _ => const Color(0xFFB54708),
    };
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(purchaseOrderStatusLabel(status)),
      labelStyle: TextStyle(color: color, fontSize: 12),
      backgroundColor: color.withValues(alpha: 0.08),
      side: BorderSide(color: color.withValues(alpha: 0.25)),
    );
  }

  Widget _fulfillmentChip(String status) {
    final isOpen = status == 'open';
    final color = isOpen ? const Color(0xFF175CD3) : const Color(0xFF475467);
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(isOpen ? 'Open' : 'Closed'),
      labelStyle: TextStyle(color: color, fontSize: 12),
      backgroundColor: color.withValues(alpha: 0.08),
      side: BorderSide(color: color.withValues(alpha: 0.25)),
    );
  }

  void _openDetail(PurchaseOrderModel order) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Expanded(child: Text('PO ${order.poNumber}')),
            _statusChip(order.status),
            IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
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
                  spacing: 28,
                  runSpacing: 14,
                  children: [
                    _detail('PO Date', _formatDate(order.poDate)),
                    _detail(
                      'Supplier',
                      '${order.supplierCode} — ${order.supplierName}',
                    ),
                    _detail('Quotation', order.quotationReference ?? '-'),
                    _detail(
                      'Requested Delivery',
                      _formatDate(order.requestedDeliveryDate),
                    ),
                    _detail('Plant', order.deliveryPlantName),
                    _detail('Payment Due', _formatDate(order.paymentDueDate)),
                    _detail('Created By', order.createdByName),
                    _detail('Reviewed By', order.reviewedByName ?? '-'),
                    _detail(
                      'Fulfillment',
                      order.fulfillmentStatus == 'open' ? 'Open' : 'Closed',
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Text('Items', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    headingRowColor: WidgetStateProperty.all(
                      const Color(0xFFF9FAFB),
                    ),
                    columns: const [
                      DataColumn(label: Text('NO')),
                      DataColumn(label: Text('PRODUCT')),
                      DataColumn(label: Text('DESCRIPTION')),
                      DataColumn(label: Text('PART NO')),
                      DataColumn(label: Text('ORDERED')),
                      DataColumn(label: Text('UNIT')),
                      DataColumn(label: Text('UNIT PRICE')),
                      DataColumn(label: Text('AMOUNT')),
                      DataColumn(label: Text('RECEIVED')),
                      DataColumn(label: Text('OUTSTANDING')),
                      DataColumn(label: Text('REMARK')),
                    ],
                    rows: order.items.indexed
                        .map(
                          (entry) => DataRow(
                            cells: [
                              DataCell(Text('${entry.$1 + 1}')),
                              DataCell(Text(entry.$2.partName)),
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
                                  'IDR ${_formatNumber(entry.$2.unitPrice)}',
                                ),
                              ),
                              DataCell(
                                Text('IDR ${_formatNumber(entry.$2.amount)}'),
                              ),
                              DataCell(
                                Text(_formatNumber(entry.$2.receivedQuantity)),
                              ),
                              DataCell(
                                Text(
                                  _formatNumber(entry.$2.outstandingQuantity),
                                ),
                              ),
                              DataCell(
                                Text(
                                  entry.$2.remark.isEmpty
                                      ? '-'
                                      : entry.$2.remark,
                                ),
                              ),
                            ],
                          ),
                        )
                        .toList(),
                  ),
                ),
                const SizedBox(height: 14),
                Align(
                  alignment: Alignment.centerRight,
                  child: SizedBox(
                    width: 310,
                    child: Column(
                      children: [
                        _totalRow('Subtotal', order.subtotal),
                        _totalRow('Discount', order.discountAmount),
                        _totalRow('PPN (${order.ppnRate}%)', order.ppnAmount),
                        _totalRow(
                          'PPh 23 (${order.pph23Rate}%)',
                          -order.pph23Amount,
                        ),
                        const Divider(),
                        _totalRow('Grand Total', order.grandTotal, bold: true),
                      ],
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
                if (order.notes.isNotEmpty) _detail('Note', order.notes),
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
              icon: const Icon(Icons.edit_outlined),
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
    width: 250,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(color: Color(0xFF667085), fontSize: 12),
        ),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
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

  Widget _totalRow(String label, double value, {bool bold = false}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        Text(
          'IDR ${_formatNumber(value)}',
          style: TextStyle(
            fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
          ),
        ),
      ],
    ),
  );

  String _formatDate(DateTime value) {
    String two(int number) => number.toString().padLeft(2, '0');
    return '${two(value.day)}/${two(value.month)}/${value.year}';
  }

  String _apiDate(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

  String _formatNumber(double value) {
    final fixed = value.toStringAsFixed(
      value.truncateToDouble() == value ? 0 : 2,
    );
    final parts = fixed.split('.');
    final chars = parts[0].split('').reversed.toList();
    final grouped = <String>[];
    for (var index = 0; index < chars.length; index++) {
      if (index > 0 && index % 3 == 0) grouped.add('.');
      grouped.add(chars[index]);
    }
    final integer = grouped.reversed.join();
    return parts.length == 1 ? integer : '$integer,${parts[1]}';
  }
}

class _PurchasingDrawer extends StatelessWidget {
  const _PurchasingDrawer({required this.auth, required this.onSelected});

  final AuthController auth;
  final ValueChanged<AppModule> onSelected;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
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
                  selected: module == AppModule.purchasing,
                  leading: Icon(module.icon),
                  title: Text(module.label),
                  onTap: () {
                    Navigator.pop(context);
                    if (module != AppModule.purchasing) onSelected(module);
                  },
                ),
              )
              .toList(),
        ),
      ),
    );
  }
}
