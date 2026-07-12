package com.ning.pm.infrastructure.storage;

public interface ObjectStorageService {

    void putObject(String objectKey, byte[] content, String contentType);

    void removeObject(String objectKey);

    String createReadUrl(String objectKey);
}
