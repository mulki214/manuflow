import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../../shared/module_navigation.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../purchasing/purchasing_page.dart';
import '../quality/quality_page.dart';
import '../receiving/receiving_page.dart';
import '../sales_order/sales_order_page.dart';
import '../users/change_password_dialog.dart';
import '../warehouse/warehouse_page.dart';
import 'production_models.dart';
import 'production_process_form_dialog.dart';
import 'production_settings_dialog.dart';
import 'wip_production_page.dart';

class ProductionPage extends StatefulWidget {
  const ProductionPage({super.key, required this.auth});

  final AuthController auth;

  @override
  State<ProductionPage> createState() => _ProductionPageState();
}

class _ProductionPageState extends State<ProductionPage> {
  final _search = TextEditingController();
  List<ProductionProcessModel> _processes = [];
  bool _checking = true;
  bool _allowed = false;
  bool _loading = false;
  String? _error;
  int _page = 1;
  int _total = 0;
  final int _size = 10;

  int get _pages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _verify();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _verify() async {
    try {
      final access = await widget.auth.refreshProductionAccess();
      if (!mounted) return;
      _allowed = access.canAccess;
      if (_allowed) await _load();
    } on ApiException catch (exception) {
      if (mounted) _error = exception.message;
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final term = _search.text.trim();
      final query = [
        'page=$_page',
        'size=$_size',
        if (term.isNotEmpty) 'search=${Uri.encodeQueryComponent(term)}',
      ].join('&');
      final response = await widget.auth.api.getJson(
        '/production/processes?$query',
      );
      if (!mounted) return;
      setState(() {
        _processes = (response['items'] as List)
            .map(
              (item) =>
                  ProductionProcessModel.fromJson(item as Map<String, dynamic>),
            )
            .toList();
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
      } else if (exception.statusCode == 403) {
        if (mounted) setState(() => _allowed = false);
      } else if (mounted) {
        setState(() => _error = exception.message);
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([ProductionProcessModel? process]) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) =>
          ProductionProcessFormDialog(api: widget.auth.api, process: process),
    );
    if (changed == true) await _load();
  }

  Future<void> _delete(ProductionProcessModel process) async {
    final confirmed = await showDeleteConfirmation(
      context,
      title: 'Delete Production Process?',
      message:
          'Delete ${process.code} — ${process.name}? Used processes cannot be deleted.',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.delete('/production/processes/${process.code}');
      await _load();
    } on ApiException catch (exception) {
      _message(exception.message);
    }
  }

  void _message(String value) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(value)));
    }
  }

  // ignore: unused_element
  void _selectModule(AppModule module) {
    Widget? page;
    if (module == AppModule.user) {
      Navigator.of(context).popUntil((route) => route.isFirst);
      return;
    }
    if (module == AppModule.masterData) {
      page = MasterDataPage(auth: widget.auth);
    }
    if (module == AppModule.purchasing && widget.auth.canAccessPurchasing) {
      page = PurchasingPage(auth: widget.auth);
    }
    if (module == AppModule.salesOrder && widget.auth.canAccessSalesOrder) {
      page = SalesOrderPage(auth: widget.auth);
    }
    if (module == AppModule.receiving && widget.auth.canAccessReceiving) {
      page = ReceivingPage(auth: widget.auth);
    }
    if (module == AppModule.warehouse && widget.auth.canAccessWarehouse) {
      page = WarehousePage(auth: widget.auth);
    }
    if (module == AppModule.quality && widget.auth.canAccessQuality) {
      page = QualityPage(auth: widget.auth);
    }
    if (page != null) {
      Navigator.of(
        context,
      ).pushReplacement(MaterialPageRoute<void>(builder: (_) => page!));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_allowed) {
      return Scaffold(
        appBar: AppBar(title: const Text('Production')),
        body: Center(
          child: Text(
            _error ??
                'Only active Production Department members can access this module.',
          ),
        ),
      );
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        final content = _content(desktop);
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(
              title: const Text('Production'),
              actions: [
                IconButton(
                  tooltip: 'WIP Production',
                  onPressed: () => Navigator.of(context).pushReplacement(
                    MaterialPageRoute<void>(
                      builder: (_) => WipProductionPage(auth: widget.auth),
                    ),
                  ),
                  icon: const Icon(Icons.account_tree_outlined),
                ),
              ],
            ),
            drawer: Drawer(
              child: SafeArea(
                child: AppSidebar(
                  auth: widget.auth,
                  activeModule: AppModule.production,
                  onModuleSelected: (module) => navigateToModule(
                    context,
                    widget.auth,
                    module,
                    activeModule: AppModule.production,
                  ),
                ),
              ),
            ),
            body: content,
            floatingActionButton: FloatingActionButton.extended(
              onPressed: _openForm,
              icon: const Icon(Icons.add),
              label: const Text('Process'),
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.production,
                onModuleSelected: (module) => navigateToModule(
                  context,
                  widget.auth,
                  module,
                  activeModule: AppModule.production,
                ),
                onChangePassword: () => showDialog<bool>(
                  context: context,
                  builder: (_) => ChangePasswordDialog(api: widget.auth.api),
                ),
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('Production')),
                  body: content,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

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
                      'Production / WIP Processes',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '$_total production and repair processes',
                      style: const TextStyle(color: Color(0xFF667085)),
                    ),
                  ],
                ),
              ),
              if (desktop)
                Wrap(
                  spacing: 10,
                  children: [
                    OutlinedButton.icon(
                      onPressed: () async {
                        await showDialog<bool>(
                          context: context,
                          barrierDismissible: false,
                          builder: (_) =>
                              ProductionSettingsDialog(api: widget.auth.api),
                        );
                      },
                      icon: const Icon(Icons.tune),
                      label: const Text('Standards & Repair Routes'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => Navigator.of(context).pushReplacement(
                        MaterialPageRoute<void>(
                          builder: (_) => WipProductionPage(auth: widget.auth),
                        ),
                      ),
                      icon: const Icon(Icons.account_tree_outlined),
                      label: const Text('WIP Production'),
                    ),
                    FilledButton.icon(
                      onPressed: _openForm,
                      icon: const Icon(Icons.add),
                      label: const Text('Create Process'),
                    ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _search,
                      onSubmitted: (_) {
                        _page = 1;
                        _load();
                      },
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.search),
                        hintText: 'Search process code or name...',
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filledTonal(
                    onPressed: () {
                      _page = 1;
                      _load();
                    },
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
              totalPages: _pages,
              totalRecords: _total,
              onPrevious: _page > 1
                  ? () {
                      _page--;
                      _load();
                    }
                  : null,
              onNext: _page < _pages
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
    if (_processes.isEmpty) {
      return const Center(child: Text('No Production Processes found.'));
    }
    return desktop ? _table() : _cards();
  }

  Widget _table() => Card(
    clipBehavior: Clip.antiAlias,
    child: ScrollableDataTable(
      child: DataTable(
        columns: const [
          DataColumn(label: Text('CODE')),
          DataColumn(label: Text('NAME')),
          DataColumn(label: Text('TYPE')),
          DataColumn(label: Text('PLANT')),
          DataColumn(label: Text('DESCRIPTION')),
          DataColumn(label: Text('STATUS')),
          DataColumn(label: Text('ACTIONS')),
        ],
        rows: _processes.map((item) => _row(item)).toList(),
      ),
    ),
  );

  DataRow _row(ProductionProcessModel item) => DataRow(
    onSelectChanged: (_) => _detail(item),
    cells: [
      DataCell(
        Text(
          item.code,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      DataCell(Text(item.name)),
      DataCell(Text(item.type.toUpperCase())),
      DataCell(Text(item.plantName)),
      DataCell(
        SizedBox(
          width: 260,
          child: Text(
            item.description,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ),
      DataCell(Chip(label: Text(item.isActive ? 'Active' : 'Inactive'))),
      DataCell(
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              onPressed: () => _openForm(item),
              tooltip: 'Edit',
              icon: const Icon(Icons.edit_outlined),
            ),
            IconButton(
              onPressed: item.canDelete ? () => _delete(item) : null,
              tooltip: 'Delete',
              icon: const Icon(Icons.delete_outline),
            ),
          ],
        ),
      ),
    ],
  );

  Widget _cards() => ListView.separated(
    padding: const EdgeInsets.only(bottom: 88),
    itemCount: _processes.length,
    separatorBuilder: (_, _) => const SizedBox(height: 10),
    itemBuilder: (context, index) {
      final item = _processes[index];
      return Card(
        child: ListTile(
          onTap: () => _detail(item),
          title: Text('${item.code} — ${item.name}'),
          subtitle: Text(
            '${item.type.toUpperCase()} • ${item.plantName}\n${item.description}',
          ),
          trailing: Icon(
            item.isActive
                ? Icons.check_circle_outline
                : Icons.pause_circle_outline,
          ),
        ),
      );
    },
  );

  void _detail(ProductionProcessModel item) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${item.code} — ${item.name}'),
        content: SizedBox(
          width: 560,
          child: Wrap(
            spacing: 24,
            runSpacing: 16,
            children: [
              _detailItem('Process Type', item.type.toUpperCase()),
              _detailItem('Plant', item.plantName),
              _detailItem('Status', item.isActive ? 'Active' : 'Inactive'),
              _detailItem(
                'Description',
                item.description.isEmpty ? '-' : item.description,
              ),
            ],
          ),
        ),
        actions: [
          OutlinedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _openForm(item);
            },
            icon: const Icon(Icons.edit_outlined),
            label: const Text('Edit'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _detailItem(String label, String value) => SizedBox(
    width: 240,
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
}
