package com.ning.demo.student.student;

import com.ning.demo.student.common.ApiResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

/** 学生档案 REST 接口；v2 新增编辑能力。 */
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
        // v2 仍未完成鉴权和幂等；该风险留到工程加固阶段处理。
        return ApiResponse.success(studentService.create(request), traceId());
    }

    @PutMapping("/{id}")
    public ApiResponse<Student> update(
            @PathVariable long id,
            @Valid @RequestBody UpdateStudentRequest request
    ) {
        return ApiResponse.success(studentService.update(id, request), traceId());
    }

    private String traceId() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}

