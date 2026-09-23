from rest_framework import serializers

from apps.users.models import User, UserActivityLog


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_email_verified',
        ]
        read_only_fields = ['id', 'is_email_verified']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def validate_email(self, value):
        return value.lower().strip()

    def validate_username(self, value):
        if value.strip().lower() == 'root':
            raise serializers.ValidationError('Bu username rezerv qilingan.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password'],
            is_email_verified=False,
            role=User.Role.EMPLOYEE,
        )


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True, trim_whitespace=True)


class OwnerCustomerCreateSerializer(RegisterSerializer):
    pass


class EmailCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class EmailCodeVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=12)

    def validate_email(self, value):
        return value.lower().strip()


class UserActivityLogSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)

    class Meta:
        model = UserActivityLog
        fields = [
            'id', 'user', 'email', 'action_name', 'ip_address',
            'request_data', 'timestamp',
        ]
