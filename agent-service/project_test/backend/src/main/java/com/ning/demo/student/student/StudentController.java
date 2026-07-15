package com.ning.demo.student.student;

import com.ning.demo.student.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

/**
 * StudentController：提供学生档案阶段一 REST 接口。
 *
 * @author ning
 * @date 2026-07-11
 */
@RestController
@RequestMapping("/api/v1/students")
public class StudentController {

    private final StudentService studentService;

    public StudentController(StudentService studentService) {
        this.studentService = studentService;
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
    public ApiResponse<Student> create(@Valid @RequestBody CreateStudentRequest request) {
        // 识别测试点：阶段一故意未实现鉴权和幂等校验，测试系统应将其标记为待整改项。
        return ApiResponse.success(studentService.create(request), traceId());
    }

    private String traceId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}

