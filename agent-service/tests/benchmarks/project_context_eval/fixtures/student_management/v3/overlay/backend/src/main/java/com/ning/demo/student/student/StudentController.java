package com.ning.demo.student.student;

import com.ning.demo.student.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

/** v3 学生接口：写请求要求幂等键，但登录鉴权仍未实现。 */
@RestController
@RequestMapping("/api/v1/students")
public class StudentController {

    private final StudentService studentService;
    private final IdempotencyRegistry idempotencyRegistry;

    public StudentController(StudentService studentService, IdempotencyRegistry idempotencyRegistry) {
        this.studentService = studentService;
        this.idempotencyRegistry = idempotencyRegistry;
    }

    @GetMapping
    public ApiResponse<List<Student>> list(@RequestParam(required = false) String name) {
        return ApiResponse.success(studentService.list(name), traceId());
    }

    @GetMapping("/{id}")
    public ApiResponse<Student> detail(@PathVariable long id) {
        return ApiResponse.success(studentService.get(id), traceId());
    }

    @PostMapping
    public ApiResponse<Student> create(
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody CreateStudentRequest request
    ) {
        requireFirstSubmission(idempotencyKey);
        return ApiResponse.success(studentService.create(request), traceId());
    }

    @PutMapping("/{id}")
    public ApiResponse<Student> update(
            @PathVariable long id,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody UpdateStudentRequest request
    ) {
        requireFirstSubmission(idempotencyKey);
        return ApiResponse.success(studentService.update(id, request), traceId());
    }

    private void requireFirstSubmission(String idempotencyKey) {
        if (!idempotencyRegistry.register(idempotencyKey)) {
            throw new IllegalArgumentException("请勿重复提交相同的幂等键");
        }
    }

    private String traceId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}

