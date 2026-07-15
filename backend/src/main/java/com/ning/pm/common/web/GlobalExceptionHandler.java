package com.ning.pm.common.web;

import cn.dev33.satoken.exception.NotLoginException;
import cn.dev33.satoken.exception.NotPermissionException;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BaseException;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.common.response.R;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.ServletRequestBindingException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * GlobalExceptionHandler 统一处理后端接口异常并返回中文错误提示。
 *
 * @author ning
 * @date 2026-06-08
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(SystemException.class)
    public R<Void> handleSystemException(SystemException exception) {
        log.error("系统异常：{}", exception.getMessage(), exception);
        return R.fail(exception.getErrorCode().getCode(), exception.getMessage());
    }

    @ExceptionHandler(BaseException.class)
    public R<Void> handleBaseException(BaseException exception) {
        log.warn("业务异常：{}", exception.getMessage());
        return R.fail(exception.getErrorCode().getCode(), exception.getMessage());
    }

    @ExceptionHandler(NotLoginException.class)
    public R<Void> handleNotLoginException(NotLoginException exception) {
        log.warn("用户未登录：{}", exception.getMessage());
        return R.fail(ErrorCode.UNAUTHORIZED.getCode(), ErrorCode.UNAUTHORIZED.getMessage());
    }

    @ExceptionHandler(NotPermissionException.class)
    public R<Void> handleNotPermissionException(NotPermissionException exception) {
        log.warn("用户无权限：{}", exception.getMessage());
        return R.fail(ErrorCode.FORBIDDEN.getCode(), ErrorCode.FORBIDDEN.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public R<Void> handleMethodArgumentNotValidException(MethodArgumentNotValidException exception) {
        log.warn("参数校验失败：{}", exception.getMessage());
        FieldError fieldError = exception.getBindingResult().getFieldError();
        String message = fieldError == null ? ErrorCode.PARAM_INVALID.getMessage() : fieldError.getDefaultMessage();
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), message);
    }

    @ExceptionHandler(BindException.class)
    public R<Void> handleBindException(BindException exception) {
        log.warn("参数绑定失败：{}", exception.getMessage());
        FieldError fieldError = exception.getBindingResult().getFieldError();
        String message = fieldError == null ? ErrorCode.PARAM_INVALID.getMessage() : fieldError.getDefaultMessage();
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), message);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public R<Void> handleConstraintViolationException(ConstraintViolationException exception) {
        log.warn("参数约束失败：{}", exception.getMessage());
        String message = exception.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .findFirst()
                .orElse(ErrorCode.PARAM_INVALID.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), message);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public R<Void> handleHttpMessageNotReadableException(HttpMessageNotReadableException exception) {
        log.warn("请求体解析失败：{}", exception.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), "请求体格式不正确");
    }

    @ExceptionHandler({ServletRequestBindingException.class, MethodArgumentTypeMismatchException.class})
    public R<Void> handleRequestBindingException(Exception exception) {
        log.warn("请求参数绑定失败：{}", exception.getMessage());
        return R.fail(ErrorCode.PARAM_INVALID.getCode(), "请求参数不完整或格式不正确");
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public R<Void> handleMaxUploadSizeExceededException(MaxUploadSizeExceededException exception) {
        log.warn("上传文件超过请求限制：{}", exception.getMessage());
        return R.fail(ErrorCode.FILE_TOO_LARGE.getCode(), ErrorCode.FILE_TOO_LARGE.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public R<Void> handleException(Exception exception) {
        log.error("系统异常", exception);
        return R.fail(ErrorCode.SYSTEM_ERROR.getCode(), ErrorCode.SYSTEM_ERROR.getMessage());
    }
}
