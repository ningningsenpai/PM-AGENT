package com.ning.pm.file.config;

import com.ning.pm.file.enums.FileBusinessType;
import org.springframework.core.convert.converter.Converter;
import org.springframework.stereotype.Component;

/**
 * StringToFileBusinessTypeConverter 支持接口使用小写business编码。
 *
 * @author ning
 * @date 2026-07-12
 */
@Component
public class StringToFileBusinessTypeConverter implements Converter<String, FileBusinessType> {

    @Override
    public FileBusinessType convert(String source) {
        return FileBusinessType.fromCode(source);
    }
}
