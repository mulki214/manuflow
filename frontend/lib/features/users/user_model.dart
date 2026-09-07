class UserModel {
  const UserModel({
    required this.id,
    required this.firstName,
    required this.lastName,
    required this.email,
    required this.gender,
    required this.role,
    required this.ktpNumber,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
    required this.accessLevel,
    this.departmentCode,
    this.departmentName,
    this.picUserId,
    this.picName,
    this.headUserId,
    this.headName,
    required this.canEdit,
    required this.canDelete,
  });

  final String id;
  final String firstName;
  final String lastName;
  final String email;
  final String gender;
  final String role;
  final String ktpNumber;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String accessLevel;
  final String? departmentCode;
  final String? departmentName;
  final String? picUserId;
  final String? picName;
  final String? headUserId;
  final String? headName;
  final bool canEdit;
  final bool canDelete;

  String get fullName => '$firstName $lastName'.trim();
  String get initials =>
      '${firstName.isEmpty ? '' : firstName[0]}${lastName.isEmpty ? '' : lastName[0]}'
          .toUpperCase();

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
    id: json['id'] as String,
    firstName: json['first_name'] as String,
    lastName: json['last_name'] as String,
    email: json['email'] as String,
    gender: json['gender'] as String,
    role: json['role'] as String,
    ktpNumber: json['ktp_number'] as String,
    isActive: json['is_active'] as bool,
    createdAt: DateTime.parse(json['created_at'] as String),
    updatedAt: DateTime.parse(json['updated_at'] as String),
    accessLevel: json['access_level'] as String? ?? 'staff',
    departmentCode: json['department_code'] as String?,
    departmentName: json['department_name'] as String?,
    picUserId: json['pic_user_id'] as String?,
    picName: json['pic_name'] as String?,
    headUserId: json['head_user_id'] as String?,
    headName: json['head_name'] as String?,
    canEdit: json['can_edit'] as bool? ?? false,
    canDelete: json['can_delete'] as bool? ?? false,
  );
}
