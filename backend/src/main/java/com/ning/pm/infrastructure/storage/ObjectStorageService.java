package com.ning.pm.infrastructure.storage;

public interface ObjectStorageService {

    void putObject(StorageLocation location, byte[] content, String contentType);

    void copyObject(StorageLocation source, StorageLocation target);

    void removeObject(StorageLocation location);

    void removeByPrefix(StorageLocation prefix);

    String createReadUrl(StorageLocation location);
}
