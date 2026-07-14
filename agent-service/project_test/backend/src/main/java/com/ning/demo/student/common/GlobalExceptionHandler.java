package com.ning.demo.student.common;

import jakarta.validation.ConstraintViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.UUID;

/**
 * GlobalExceptionHandler：将校验、业务和系统异常转换为中文统一响应。
 *
 * @author ning
 * @date 2026-07-11
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(StudentNotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNotFound(StudentNotFoundException exception) {
        return ResponseEntity.status(404).body(ApiResponse.error(20001, exception.getMessage(), traceId()));
    }

    @ExceptionHandler(DuplicateKeyException.class)
    public ResponseEntity<ApiResponse<Void>> handleDuplicate(DuplicateKeyException exception) {
        return ResponseEntity.badRequest().body(ApiResponse.error(20002, "学号已存在", traceId()));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, ConstraintViolationException.class})
    public ResponseEntity<ApiResponse<Void>> handleValidation(Exception exception) {
        String message = exception instanceof MethodArgumentNotValidException validationException
                ? validationException.getBindingResult().getAllErrors().get(0).getDefaultMessage()
                : exception.getMessage();
        return ResponseEntity.badRequest().body(ApiResponse.error(10001, message, traceId()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnknown(Exception exception) {
        return ResponseEntity.internalServerError()
                .body(ApiResponse.error(90000, "系统繁忙，请稍后重试", traceId()));
    }

    private String traceId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}
