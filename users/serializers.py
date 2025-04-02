from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        exclude = ('groups', 'user_permissions', 'is_active', 'is_staff', 'is_superuser',)
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class UserGet(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('uuid', 'avatar', 'first_name', 'last_name', 'surname', 'email', 'about')


class FireUser(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('termination_reason', 'termination_order_date', 'termination_date')

class UserChangePassword(serializers.Serializer):
    new_password = serializers.CharField()

class UserRegistration(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
    

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        refresh_token = RefreshToken(attrs['refresh'])
        user_id = refresh_token['user_id']
        
        try:
            user = User.objects.get(uuid=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь не найден.")
        
        new_refresh = RefreshToken.for_user(user)
        
        data['refresh'] = str(new_refresh)
        return data