-- Ejecutar conectado como administrador de Microsoft Entra del servidor SQL.
-- Reemplaza secureauth-store por el nombre exacto de la identidad administrada de App Service.
CREATE USER [secureauth-store] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [secureauth-store];
ALTER ROLE db_datawriter ADD MEMBER [secureauth-store];

-- La identidad de ejecución NO recibe db_owner ni permisos DDL.
-- Las migraciones deben ejecutarse con una identidad separada y controlada.
