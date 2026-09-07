import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../shared/app_sidebar.dart';
import '../../shared/crud_widgets.dart';
import '../auth/auth_controller.dart';
import '../master_data/master_data_page.dart';
import '../purchasing/purchasing_page.dart';
import '../production/production_page.dart';
import '../quality/quality_page.dart';
import '../finish_good/finish_good_page.dart';
import '../dashboard/dashboard_page.dart';
import '../delivery/delivery_page.dart';
import '../reporting/reporting_page.dart';
import '../sales_order/sales_order_page.dart';
import '../receiving/receiving_page.dart';
import '../warehouse/warehouse_page.dart';
import 'user_form_dialog.dart';
import 'user_model.dart';
import 'change_password_dialog.dart';

class UserPage extends StatefulWidget {
  const UserPage({super.key, required this.auth, this.embedded = false});
  final AuthController auth;
  final bool embedded;

  @override
  State<UserPage> createState() => _UserPageState();
}

class _UserPageState extends State<UserPage> {
  final _search = TextEditingController();
  List<UserModel> _users = [];
  bool _loading = true;
  String? _error;
  int _page = 1;
  final int _size = 10;
  int _total = 0;

  int get _totalPages => _total == 0 ? 1 : (_total / _size).ceil();

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _loadUsers() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final search = _search.text.trim();
    final query = [
      'page=$_page',
      'size=$_size',
      if (search.isNotEmpty) 'search=${Uri.encodeQueryComponent(search)}',
    ].join('&');
    try {
      final response = await widget.auth.api.getJson('/users?$query');
      if (!mounted) return;
      setState(() {
        _users = (response['items'] as List)
            .map((item) => UserModel.fromJson(item as Map<String, dynamic>))
            .toList();
        _total = response['total'] as int;
      });
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) {
        await widget.auth.logout();
        return;
      }
      if (mounted) setState(() => _error = exception.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Tidak dapat memuat data user');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm([UserModel? user]) async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => UserFormDialog(api: widget.auth.api, user: user),
    );
    if (changed == true) {
      await _loadUsers();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              user == null
                  ? 'User berhasil ditambahkan'
                  : 'User berhasil diperbarui',
            ),
          ),
        );
      }
    }
  }

  Future<void> _deleteUser(UserModel user) async {
    final confirmed = await showDeleteConfirmation(
      context,
      title: 'Delete User?',
      message:
          'Are you sure you want to delete ${user.id} — ${user.fullName}? The user will no longer be able to log in.',
    );
    if (!confirmed) return;
    try {
      await widget.auth.api.delete('/users/${user.id}');
      if (_users.length == 1 && _page > 1) _page--;
      await _loadUsers();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('User berhasil dihapus')));
      }
    } on ApiException catch (exception) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(exception.message)));
      }
    }
  }

  void _openDetail(UserModel user) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            const Expanded(child: Text('User Detail')),
            IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                _DetailField(label: 'User ID', value: user.id),
                _DetailField(label: 'Full Name', value: user.fullName),
                _DetailField(label: 'Email', value: user.email),
                _DetailField(
                  label: 'Gender',
                  value: user.gender == 'male' ? 'Male' : 'Female',
                ),
                _DetailField(label: 'Position / Role', value: user.role),
                _DetailField(label: 'Access Level', value: user.accessLevel),
                _DetailField(
                  label: 'Department',
                  value: user.departmentName ?? '-',
                ),
                _DetailField(label: 'PIC Name', value: user.picName ?? '-'),
                _DetailField(label: 'Head Name', value: user.headName ?? '-'),
                _DetailField(label: 'KTP Number', value: user.ktpNumber),
                _DetailField(
                  label: 'Status',
                  value: user.isActive ? 'Active' : 'Inactive',
                ),
                _DetailField(
                  label: 'Created At',
                  value: _formatDateTime(user.createdAt),
                ),
                _DetailField(
                  label: 'Updated At',
                  value: _formatDateTime(user.updatedAt),
                ),
              ],
            ),
          ),
        ),
        actions: [
          OutlinedButton.icon(
            onPressed: user.canEdit
                ? () {
                    Navigator.pop(context);
                    _openForm(user);
                  }
                : null,
            icon: const Icon(Icons.edit_outlined),
            label: const Text('Edit'),
          ),
        ],
      ),
    );
  }

  String _formatDateTime(DateTime value) {
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${two(local.day)}/${two(local.month)}/${local.year} ${two(local.hour)}:${two(local.minute)}';
  }

  void _selectModule(BuildContext context, AppModule module) {
    if (module == AppModule.dashboard) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => DashboardPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.masterData) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => MasterDataPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.salesOrder &&
        widget.auth.canAccessSalesOrder) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => SalesOrderPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.purchasing &&
        widget.auth.canAccessPurchasing) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => PurchasingPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.receiving &&
        widget.auth.canAccessReceiving) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ReceivingPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.warehouse &&
        widget.auth.canAccessWarehouse) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => WarehousePage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.production &&
        widget.auth.canAccessProduction) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ProductionPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.quality && widget.auth.canAccessQuality) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => QualityPage(auth: widget.auth)),
      );
    } else if (module == AppModule.finishGood &&
        widget.auth.canAccessFinishGood) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => FinishGoodPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.delivery && widget.auth.canAccessDelivery) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => DeliveryPage(auth: widget.auth),
        ),
      );
    } else if (module == AppModule.reporting) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => ReportingPage(auth: widget.auth),
        ),
      );
    }
  }

  Future<void> _changePassword() async {
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ChangePasswordDialog(api: widget.auth.api),
    );
    if (changed == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password berhasil diperbarui')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1000;
        if (widget.embedded) return _content(desktop);
        if (!desktop) {
          return Scaffold(
            appBar: AppBar(
              title: const Text(
                'Manuflow ERP',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              actions: [
                IconButton(
                  onPressed: _changePassword,
                  tooltip: 'Change Password',
                  icon: const Icon(Icons.password_outlined),
                ),
                IconButton(
                  onPressed: widget.auth.logout,
                  tooltip: 'Keluar',
                  icon: const Icon(Icons.logout),
                ),
              ],
            ),
            drawer: _AppDrawer(
              auth: widget.auth,
              onModuleSelected: (module) => _selectModule(context, module),
            ),
            body: _content(desktop),
            floatingActionButton: FloatingActionButton.extended(
              onPressed: _openForm,
              icon: const Icon(Icons.person_add_alt_1),
              label: const Text('Tambah'),
            ),
          );
        }
        return Scaffold(
          body: Row(
            children: [
              AppSidebar(
                auth: widget.auth,
                activeModule: AppModule.user,
                onModuleSelected: (module) => _selectModule(context, module),
                onChangePassword: _changePassword,
              ),
              Expanded(
                child: Scaffold(
                  appBar: AppBar(title: const Text('User')),
                  body: _content(desktop),
                ),
              ),
            ],
          ),
        );
      },
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
                        'Manajemen User',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '$_total user aktif',
                        style: const TextStyle(color: Color(0xFF667085)),
                      ),
                    ],
                  ),
                ),
                if (desktop)
                  FilledButton.icon(
                    onPressed: _openForm,
                    icon: const Icon(Icons.add),
                    label: const Text('Tambah User'),
                  ),
              ],
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _search,
                        onSubmitted: (_) {
                          _page = 1;
                          _loadUsers();
                        },
                        decoration: const InputDecoration(
                          hintText: 'Cari nama, email, atau ID user...',
                          prefixIcon: Icon(Icons.search),
                          isDense: true,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    IconButton.filledTonal(
                      onPressed: () {
                        _page = 1;
                        _loadUsers();
                      },
                      tooltip: 'Cari',
                      icon: const Icon(Icons.search),
                    ),
                    IconButton(
                      onPressed: _loadUsers,
                      tooltip: 'Muat ulang',
                      icon: const Icon(Icons.refresh),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Expanded(child: _body(desktop)),
            if (!_loading && _error == null)
              CrudPaginationBar(
                currentPage: _page,
                totalPages: _totalPages,
                totalRecords: _total,
                onPrevious: _page > 1
                    ? () {
                        _page--;
                        _loadUsers();
                      }
                    : null,
                onNext: _page < _totalPages
                    ? () {
                        _page++;
                        _loadUsers();
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
            const Icon(
              Icons.cloud_off_outlined,
              size: 48,
              color: Color(0xFF98A2B3),
            ),
            const SizedBox(height: 12),
            Text(_error!),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _loadUsers,
              child: const Text('Coba lagi'),
            ),
          ],
        ),
      );
    }
    if (_users.isEmpty) {
      return const Center(child: Text('Belum ada user yang ditemukan.'));
    }
    return desktop ? _desktopTable() : _mobileList();
  }

  Widget _desktopTable() {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: SingleChildScrollView(
        child: SizedBox(
          width: double.infinity,
          child: DataTable(
            showCheckboxColumn: false,
            headingRowColor: WidgetStateProperty.all(const Color(0xFFF9FAFB)),
            columns: const [
              DataColumn(label: Text('USER')),
              DataColumn(label: Text('ID')),
              DataColumn(label: Text('POSITION / ROLE')),
              DataColumn(label: Text('DEPARTMENT')),
              DataColumn(label: Text('ACTIONS')),
            ],
            rows: _users
                .map(
                  (user) => DataRow(
                    onSelectChanged: (_) => _openDetail(user),
                    cells: [
                      DataCell(_UserIdentity(user: user)),
                      DataCell(
                        Text(
                          user.id,
                          style: const TextStyle(fontFamily: 'monospace'),
                        ),
                      ),
                      DataCell(Text(user.role)),
                      DataCell(Text(user.departmentName ?? '-')),
                      DataCell(_actions(user)),
                    ],
                  ),
                )
                .toList(),
          ),
        ),
      ),
    );
  }

  Widget _mobileList() {
    return ListView.separated(
      padding: const EdgeInsets.only(bottom: 88),
      itemCount: _users.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final user = _users[index];
        return Card(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => _openDetail(user),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: _UserIdentity(user: user)),
                      _actions(user),
                    ],
                  ),
                  const Divider(height: 28),
                  Wrap(
                    spacing: 16,
                    runSpacing: 8,
                    children: [
                      _Meta(icon: Icons.badge_outlined, label: user.id),
                      _Meta(icon: Icons.work_outline, label: user.role),
                      _Meta(
                        icon: Icons.apartment_outlined,
                        label: user.departmentName ?? '-',
                      ),
                      _Meta(
                        icon: Icons.person_outline,
                        label: user.gender == 'male' ? 'Male' : 'Female',
                      ),
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

  Widget _actions(UserModel user) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          tooltip: 'Edit',
          onPressed: user.canEdit ? () => _openForm(user) : null,
          icon: const Icon(Icons.edit_outlined),
        ),
        IconButton(
          tooltip: user.canDelete ? 'Delete' : 'No permission to delete',
          onPressed: user.canDelete ? () => _deleteUser(user) : null,
          color: Theme.of(context).colorScheme.error,
          icon: const Icon(Icons.delete_outline),
        ),
      ],
    );
  }
}

class _UserIdentity extends StatelessWidget {
  const _UserIdentity({required this.user});
  final UserModel user;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircleAvatar(
          backgroundColor: const Color(0xFFD1E9FF),
          child: Text(
            user.initials,
            style: const TextStyle(
              color: Color(0xFF175CD3),
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                user.fullName,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              Text(
                user.email,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Color(0xFF667085), fontSize: 13),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta({required this.icon, required this.label});
  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 16, color: const Color(0xFF667085)),
      const SizedBox(width: 6),
      Text(
        label,
        style: const TextStyle(fontSize: 13, color: Color(0xFF475467)),
      ),
    ],
  );
}

class _DetailField extends StatelessWidget {
  const _DetailField({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
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
  }
}

class _AppDrawer extends StatelessWidget {
  const _AppDrawer({required this.auth, required this.onModuleSelected});
  final AuthController auth;
  final ValueChanged<AppModule> onModuleSelected;

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
                        selected: module == AppModule.user,
                        leading: Icon(module.icon),
                        title: Text(module.label),
                        onTap: () {
                          Navigator.pop(context);
                          if (module != AppModule.user) {
                            onModuleSelected(module);
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
