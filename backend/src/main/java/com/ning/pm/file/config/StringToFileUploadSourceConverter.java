package com.ning.pm.file.config;

import com.ning.pm.file.enums.FileUploadSource;
import org.springframework.core.convert.converter.Converter;
import org.springframework.stereotype.Component;

/**
 * StringToFileUploadSourceConverter 支持接口使用小写上传来源编码。
 *
 * @author ning
 * @date 2026-07-12
 */
@Component
public class StringToFileUploadSourceConverter implements Converter<String, FileUploadSource> {

    @Override
    public FileUploadSource convert(String source) {
        return FileUploadSource.fromCode(source);
    }
}
